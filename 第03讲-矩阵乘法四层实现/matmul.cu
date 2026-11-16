/*
 * 第03讲 矩阵乘法四层实现 —— 第 4 层：CUDA（一线程算一个 C[i][j]）
 *
 * 规格：3x3 整数矩阵 C = A x B
 * 线程映射：blockDim = (32, 32)，一个线程负责一个 C[row][col]
 *           gridDim = ( ceil(N/32), ceil(N/32) ) = (1, 1)  → 只需 1 个 block
 *           该 block 共 32*32 = 1024 个线程，其中只有 3*3 = 9 个线程真正计算
 *           有效利用率 9/1024 ≈ 0.88%   ← 3x3 太小，GPU 完全喂不饱
 *
 * ⚠ 本机情况（如实记录）：本机确有 NVIDIA GeForce RTX 4060 Laptop GPU，
 *   但**未安装 CUDA Toolkit（无 nvcc）**，因此本文件**未编译、未运行**，
 *   只做静态实现与逐行说明。
 *   为证明「核函数的算法与 C 版完全一致」，另附 matmul_cu_ref.c ——
 *   它与本文件内核的累加循环逐行同构，已在 cl 下真实编译运行，
 *   CHECKSUM = 621，与 C/Verilog/NumPy 三层一致（见日志 run_cu_ref.txt）。
 *
 * MUSA 迁移（指南第 8 步）：把下面的 cuda 前缀全部换成 musa 即得摩尔线程版本，
 *   见 matmul_musa.cu 与 musa_diff.txt 的真实 diff 统计。
 */
#include <stdio.h>
#include <stdlib.h>

#define N 3
#define BLK 32          /* blockDim.x = blockDim.y = 32 */

/* ============================================================
 *  GPU 核函数：一个线程算一个 C[i][j]
 * ============================================================ */
__global__ void matmul_kernel(const int *A, const int *B, int *C, int n)
{
    /* 线程在 2D 网格中的坐标 → 输出矩阵的行列号 */
    int col = blockIdx.x * blockDim.x + threadIdx.x;   /* j */
    int row = blockIdx.y * blockDim.y + threadIdx.y;   /* i */

    /*
     * 越界判断：必须写。
     * 3x3 只用到 32x32 线程块左上角的 9 个线程，其余 1015 个线程
     * 若不加这个 return 就会越界读写 → 直接崩（指南「常见问题」第 4 条）。
     */
    if (row < n && col < n) {
        int sum = 0;
        for (int k = 0; k < n; ++k)
            sum += A[row * n + k] * B[k * n + col];
        C[row * n + col] = sum;
    }
}

/* ============================================================
 *  Host 端：分配显存 → 拷入 → 启动 1 个 block → 拷回
 * ============================================================ */
int main(void)
{
    /* 测试数据与 matmul.c 完全相同 */
    int h_A[N][N] = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    int h_B[N][N] = {{9, 8, 7}, {6, 5, 4}, {3, 2, 1}};
    int h_C[N][N];
    int *d_A, *d_B, *d_C;
    size_t bytes = N * N * sizeof(int);
    int i, j;
    long checksum = 0;

    /* 1. 分配设备内存 */
    cudaMalloc((void **)&d_A, bytes);
    cudaMalloc((void **)&d_B, bytes);
    cudaMalloc((void **)&d_C, bytes);

    /* 2. 主机 → 设备 */
    cudaMemcpy(d_A, h_A, bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_B, h_B, bytes, cudaMemcpyHostToDevice);

    /* 3. 配置网格：32x32 一个 block 就够 3x3 */
    dim3 blockDim(BLK, BLK, 1);                       /* 1024 线程 */
    dim3 gridDim((N + BLK - 1) / BLK,                 /* = 1 */
                 (N + BLK - 1) / BLK,                 /* = 1 */
                 1);
    printf("=== CUDA 版 matmul (N=%d) ===\n", N);
    printf("blockDim = (%d, %d) = %d 线程/block\n", BLK, BLK, BLK * BLK);
    printf("gridDim  = (%d, %d) -> %d 个 block\n",
           gridDim.x, gridDim.y, gridDim.x * gridDim.y);
    printf("总线程数 = %d，实际计算 = %d，利用率 = %.2f%%\n",
           gridDim.x * gridDim.y * BLK * BLK, N * N,
           100.0 * N * N / (gridDim.x * gridDim.y * BLK * BLK));

    /* 4. 启动核函数：<<<grid, block>>> 里 9 个线程并行算 9 个 C[i][j] */
    matmul_kernel<<<gridDim, blockDim>>>(d_A, d_B, d_C, N);
    cudaDeviceSynchronize();

    /* 5. 设备 → 主机 */
    cudaMemcpy(h_C, d_C, bytes, cudaMemcpyDeviceToHost);

    printf("C = A x B =\n");
    for (i = 0; i < N; i++) {
        printf("  [");
        for (j = 0; j < N; j++) printf(" %4d", h_C[i][j]);
        printf(" ]\n");
    }
    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++)
            checksum += h_C[i][j];
    printf("CHECKSUM = %ld\n", checksum);

    cudaFree(d_A);
    cudaFree(d_B);
    cudaFree(d_C);
    return 0;
}
