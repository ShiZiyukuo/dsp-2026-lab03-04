/*
 * matmul_cu_bench.cu —— CUDA 真机性能对比（第03讲 拓展用）
 *
 * 目的：3x3 太小，GPU 完全体现不出并行优势；这里把 N 放大到 512/1024，
 *       用 cudaEventRecord 真测 kernel 时间，和 CPU 三重循环对比，
 *       并额外给一个 shared-memory Tiling 版本，量化「分块为什么能提速」。
 *
 * 编译（需 vcvars64 环境）：
 *   nvcc -O2 -arch=sm_89 -DN=1024 matmul_cu_bench.cu -o ..\build\matmul_cu_bench.exe
 * 运行（需把 cudart DLL 目录加进 PATH）：
 *   matmul_cu_bench.exe
 *
 * 所有数字都是本机真跑出来的，没有任何预设。
 */
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <cuda_runtime.h>

#ifndef N
#define N 1024
#endif

#define TILE 16          /* Tiling 版的分块边长 */
#define BLKX 32          /* 教学版 / naive 版的 blockDim.x */
#define BLKY 32
#define REPEAT 50        /* 计时重复次数，取中位 */

/* ---------------- 工具：CUDA 错误检查 ---------------- */
#define CK(expr)                                                              \
    do {                                                                      \
        cudaError_t _e = (expr);                                              \
        if (_e != cudaSuccess) {                                              \
            printf("[CUDA ERROR] %s -> %s\n", #expr, cudaGetErrorString(_e)); \
            exit(1);                                                          \
        }                                                                     \
    } while (0)

/* ---------------- 测试数据：确定性填充，CPU/GPU 用同一份 ---------------- */
static void fill(int *a, int n, unsigned seed)
{
    unsigned s = seed;
    for (int i = 0; i < n * n; ++i) {
        s = s * 1103515245u + 12345u;      /* LCG，跨平台确定 */
        a[i] = (int)((s >> 16) % 10);      /* 0..9，保证累加不溢出 int */
    }
}

/* ---------------- CPU 参考实现：i-j-k 三重循环 ---------------- */
static void matmul_cpu(const int *A, const int *B, int *C, int n)
{
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) {
            int sum = 0;
            for (int k = 0; k < n; ++k)
                sum += A[i * n + k] * B[k * n + j];
            C[i * n + j] = sum;
        }
}

/* ---------------- GPU 核函数 1：一线程一个 C[i][j]（教学版同款） ---------------- */
__global__ void kernel_naive(const int *A, const int *B, int *C, int n)
{
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    if (row < n && col < n) {
        int sum = 0;
        for (int k = 0; k < n; ++k)
            sum += A[row * n + k] * B[k * n + col];
        C[row * n + col] = sum;
    }
}

/* ---------------- GPU 核函数 2：shared-memory Tiling ---------------- */
__global__ void kernel_tiled(const int *A, const int *B, int *C, int n)
{
    __shared__ int As[TILE][TILE];
    __shared__ int Bs[TILE][TILE];

    int tx = threadIdx.x, ty = threadIdx.y;
    int row = blockIdx.y * TILE + ty;
    int col = blockIdx.x * TILE + tx;
    int sum = 0;

    for (int t = 0; t < (n + TILE - 1) / TILE; ++t) {
        /* 每个线程搬一个元素进共享内存（越界补 0） */
        int aRow = row, aCol = t * TILE + tx;
        As[ty][tx] = (aRow < n && aCol < n) ? A[aRow * n + aCol] : 0;
        int bRow = t * TILE + ty, bCol = col;
        Bs[ty][tx] = (bRow < n && bCol < n) ? B[bRow * n + bCol] : 0;

        __syncthreads();

        for (int k = 0; k < TILE; ++k)
            sum += As[ty][k] * Bs[k][tx];

        __syncthreads();
    }
    if (row < n && col < n)
        C[row * n + col] = sum;
}

/* ---------------- 计时：warmup + REPEAT 次，返回中位毫秒 ---------------- */
static int cmp_double(const void *a, const void *b)
{
    double x = *(const double *)a, y = *(const double *)b;
    return (x < y) ? -1 : (x > y) ? 1 : 0;
}

static double time_kernel(void (*launch)(const int *, const int *, int *, int),
                          const int *dA, const int *dB, int *dC, int n,
                          const char *tag)
{
    double ms[REPEAT];
    cudaEvent_t e0, e1;
    CK(cudaEventCreate(&e0));
    CK(cudaEventCreate(&e1));

    /* warmup：让 GPU 时钟升上去、把首次的初始化成本排除掉 */
    for (int i = 0; i < 5; ++i) launch(dA, dB, dC, n);
    CK(cudaDeviceSynchronize());

    for (int i = 0; i < REPEAT; ++i) {
        float fms = 0.0f;              /* CUDA 13 起 cudaEventElapsedTime 只接受 float* */
        CK(cudaEventRecord(e0));
        launch(dA, dB, dC, n);
        CK(cudaEventRecord(e1));
        CK(cudaEventSynchronize(e1));
        CK(cudaEventElapsedTime(&fms, e0, e1));
        ms[i] = (double)fms;
    }
    CK(cudaEventDestroy(e0));
    CK(cudaEventDestroy(e1));

    qsort(ms, REPEAT, sizeof(double), cmp_double);
    double med = ms[REPEAT / 2];
    printf("  %-18s kernel 用时中位 = %8.4f ms   (min %.4f / max %.4f, %d 次)\n",
           tag, med, ms[0], ms[REPEAT - 1], REPEAT);
    return med;
}

/* launch 包装（把 <<<>>> 语法藏进函数指针） */
static void launch_naive(const int *A, const int *B, int *C, int n)
{
    dim3 blk(BLKX, BLKY);
    dim3 grd((n + BLKX - 1) / BLKX, (n + BLKY - 1) / BLKY);
    kernel_naive<<<grd, blk>>>(A, B, C, n);
}

static void launch_tiled(const int *A, const int *B, int *C, int n)
{
    dim3 blk(TILE, TILE);
    dim3 grd((n + TILE - 1) / TILE, (n + TILE - 1) / TILE);
    kernel_tiled<<<grd, blk>>>(A, B, C, n);
}

int main(void)
{
    const int n = N;
    size_t bytes = (size_t)n * n * sizeof(int);

    printf("=== CUDA 真机基准：%dx%d 整数矩阵乘法 ===\n", n, n);

    /* ---------- 1. 设备属性（一律来自 cudaGetDeviceProperties） ---------- */
    cudaDeviceProp prop;
    CK(cudaGetDeviceProperties(&prop, 0));
    printf("--- 设备属性 (cudaGetDeviceProperties) ---\n");
    printf("  device name          : %s\n", prop.name);
    printf("  compute capability   : %d.%d  (sm_%d%d)\n",
           prop.major, prop.minor, prop.major, prop.minor);
    printf("  multiprocessor 数    : %d\n", prop.multiProcessorCount);
    printf("  每 block 最大线程数  : %d\n", prop.maxThreadsPerBlock);
    printf("  全局显存             : %.2f GiB (%zu 字节)\n",
           prop.totalGlobalMem / 1073741824.0, prop.totalGlobalMem);
    printf("  显存总线宽度         : %d bit\n", prop.memoryBusWidth);
    printf("  共享内存/block       : %zu 字节\n", prop.sharedMemPerBlock);
    printf("  CUDA 运行时版本      : %d\n", (int)CUDART_VERSION);

    /* ---------- 2. 准备数据 ---------- */
    int *hA = (int *)malloc(bytes);
    int *hB = (int *)malloc(bytes);
    int *hC = (int *)malloc(bytes);
    int *hRef = (int *)malloc(bytes);
    fill(hA, n, 12345u);
    fill(hB, n, 67890u);

    int *dA, *dB, *dC;
    CK(cudaMalloc(&dA, bytes));
    CK(cudaMalloc(&dB, bytes));
    CK(cudaMalloc(&dC, bytes));
    CK(cudaMemcpy(dA, hA, bytes, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dB, hB, bytes, cudaMemcpyHostToDevice));

    /* ---------- 3. CPU 参考 + 计时 ---------- */
    clock_t c0 = clock();
    matmul_cpu(hA, hB, hRef, n);
    clock_t c1 = clock();
    double cpu_ms = (double)(c1 - c0) * 1000.0 / CLOCKS_PER_SEC;
    printf("--- CPU 参考实现 (i-j-k 三重循环) ---\n");
    printf("  用时 = %.2f ms\n", cpu_ms);

    long long cpu_sum = 0;
    for (size_t i = 0; i < (size_t)n * n; ++i) cpu_sum += hRef[i];
    printf("  CHECKSUM = %lld\n", cpu_sum);

    /* ---------- 4. GPU naive ---------- */
    printf("--- GPU kernel ---\n");
    double t_naive = time_kernel(launch_naive, dA, dB, dC, n,
                                 "naive 1 thread/元素");
    CK(cudaMemcpy(hC, dC, bytes, cudaMemcpyDeviceToHost));
    long long gpu_sum = 0;
    int mismatch = 0;
    for (size_t i = 0; i < (size_t)n * n; ++i) {
        gpu_sum += hC[i];
        if (hC[i] != hRef[i]) ++mismatch;
    }
    printf("  GPU CHECKSUM = %lld   与 CPU 逐元素不一致个数 = %d\n", gpu_sum, mismatch);

    /* ---------- 5. GPU tiled ---------- */
    double t_tiled = time_kernel(launch_tiled, dA, dB, dC, n,
                                 "tiled 16x16 共享内存");
    CK(cudaMemcpy(hC, dC, bytes, cudaMemcpyDeviceToHost));
    long long tiled_sum = 0;
    int mismatch2 = 0;
    for (size_t i = 0; i < (size_t)n * n; ++i) {
        tiled_sum += hC[i];
        if (hC[i] != hRef[i]) ++mismatch2;
    }
    printf("  Tiled CHECKSUM = %lld  与 CPU 不一致个数 = %d\n", tiled_sum, mismatch2);

    /* ---------- 6. 汇总 ---------- */
    printf("--- 汇总 (N=%d) ---\n", n);
    printf("  CPU 三重循环        : %9.2f ms\n", cpu_ms);
    printf("  GPU naive kernel    : %9.4f ms   相对 CPU 加速 %.2fx\n",
           t_naive, cpu_ms / t_naive);
    printf("  GPU tiled kernel    : %9.4f ms   相对 CPU 加速 %.2fx   相对 naive 加速 %.2fx\n",
           t_tiled, cpu_ms / t_tiled, t_naive / t_tiled);
    printf("  结果一致性          : naive %s / tiled %s\n",
           mismatch == 0 ? "PASS(全部一致)" : "FAIL",
           mismatch2 == 0 ? "PASS(全部一致)" : "FAIL");

    free(hA); free(hB); free(hC); free(hRef);
    CK(cudaFree(dA)); CK(cudaFree(dB)); CK(cudaFree(dC));
    return (mismatch == 0 && mismatch2 == 0) ? 0 : 1;
}
