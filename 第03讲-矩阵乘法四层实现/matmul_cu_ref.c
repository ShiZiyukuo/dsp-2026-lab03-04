/*
 * matmul_cu_ref.c —— matmul.cu 内核算法语义的无 GPU 验证件
 *
 * 本机未装 CUDA Toolkit（无 nvcc），matmul.cu 无法编译运行。
 * 为了不「凭嘴说结果一致」，这里把 matmul.cu 核函数里的累加循环
 * 原样搬到 CPU 上（逐行同构），用 cl 真实编译运行，证明：
 *   同一个算法、同一组输入 → CHECKSUM = 621，与 C / NumPy / Verilog 一致。
 *
 * 与核函数的对应关系：
 *   核函数的 (row, col)  ← 本文件的二重循环下标 i, j
 *   核函数的 if(row<n && col<n)  ← 本文件的循环边界 i<N, j<N
 *   核函数的 for(k) sum += ...   ← 本文件完全相同的 for(k) sum += ...
 */
#include <stdio.h>

#define N 3

int main(void)
{
    int A[N][N] = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
    int B[N][N] = {{9, 8, 7}, {6, 5, 4}, {3, 2, 1}};
    int C[N][N];
    int i, j, k;
    long checksum = 0;
    int passed = 0;

    printf("=== matmul.cu 核函数语义的 CPU 等价验证 (N=%d) ===\n", N);
    printf("（本机无 CUDA Toolkit，故 matmul.cu 未编译；此处验证其算法）\n");

    /* 与 matmul_kernel 内部完全相同的计算：一个 (i,j) 一个 sum */
    for (i = 0; i < N; ++i) {
        for (j = 0; j < N; ++j) {
            int sum = 0;
            for (k = 0; k < N; ++k)
                sum += A[i][k] * B[k][j];
            C[i][j] = sum;
        }
    }

    printf("C = A x B =\n");
    for (i = 0; i < N; i++) {
        printf("  [");
        for (j = 0; j < N; j++) printf(" %4d", C[i][j]);
        printf(" ]\n");
    }
    printf("C_FLAT =");
    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++)
            printf(" %d", C[i][j]);
    printf("\n");

    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++) {
            checksum += C[i][j];
            if (C[i][j] == (int[]){30,24,18,84,69,54,138,114,90}[i * N + j])
                passed++;
        }
    printf("CHECKSUM = %ld\n", checksum);
    printf("RESULT: %d/9 PASS  ==> %s\n", passed,
           passed == 9 ? "ALL PASS" : "MISMATCH");
    printf("结论：CUDA 内核的算法在 CPU 等价实现下与 C 版逐项一致（621）。\n");
    return (passed == 9) ? 0 : 1;
}
