/*
 * 第03讲 矩阵乘法四层实现 —— 第 1 层：C 语言（三重循环）
 * 规格：3x3 整数矩阵 C = A x B
 * 编译：gcc -O0 -o matmul matmul.c      （另测 -O2）
 * 运行：./matmul
 *
 * 输出内容：
 *   1) A、B、C 三个矩阵（C 为计算结果）
 *   2) 校验和 checksum = sum(C[i][j])
 *   3) 与硬编码标准答案逐项比对（PASS/FAIL）
 *   4) 可选：把 C 打印成 "C = a b c; d e f; g h i" 一行，便于与
 *      Verilog testbench / CUDA 输出的同一行做逐字符 diff。
 */
#include <stdio.h>

#define N 3

/* 测试数据：固定一组，保证四层实现可用同一组输入 */
static const int A[N][N] = {
    {1, 2, 3},
    {4, 5, 6},
    {7, 8, 9}
};
static const int B[N][N] = {
    {9, 8, 7},
    {6, 5, 4},
    {3, 2, 1}
};

/* 标准答案：由 NumPy( dtype=int64 ) A @ B 得到，硬编码在这里做逐项比对 */
static const int REF[N][N] = {
    { 30,  24,  18},
    { 84,  69,  54},
    {138, 114,  90}
};

int main(void)
{
    int C[N][N];
    int i, j, k;
    long checksum = 0;
    int passed = 0, total = 0;

    /* ---------- 1. 三重循环矩阵乘法 ---------- */
    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            C[i][j] = 0;
            for (k = 0; k < N; k++) {
                C[i][j] += A[i][k] * B[k][j];
            }
        }
    }

    /* ---------- 2. 打印输入 ---------- */
    printf("=== C 语言三重循环实现 3x3 矩阵乘法 (N=%d) ===\n", N);
    printf("A =\n");
    for (i = 0; i < N; i++) {
        printf("  [");
        for (j = 0; j < N; j++) printf(" %4d", A[i][j]);
        printf(" ]\n");
    }
    printf("B =\n");
    for (i = 0; i < N; i++) {
        printf("  [");
        for (j = 0; j < N; j++) printf(" %4d", B[i][j]);
        printf(" ]\n");
    }

    /* ---------- 3. 打印结果 ---------- */
    printf("C = A x B =\n");
    for (i = 0; i < N; i++) {
        printf("  [");
        for (j = 0; j < N; j++) printf(" %4d", C[i][j]);
        printf(" ]\n");
    }

    /* 一行可 diff 形式，供其他三层实现做字符串级对比 */
    printf("C_FLAT =");
    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++)
            printf(" %d", C[i][j]);
    printf("\n");

    /* ---------- 4. 校验和 ---------- */
    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++)
            checksum += C[i][j];
    printf("CHECKSUM = %ld\n", checksum);

    /* ---------- 5. 与标准答案逐项比对 ---------- */
    printf("--- 与标准答案逐项比对 ---\n");
    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            total++;
            if (C[i][j] == REF[i][j]) {
                passed++;
                printf("  C[%d][%d] = %4d  REF = %4d  PASS\n",
                       i, j, C[i][j], REF[i][j]);
            } else {
                printf("  C[%d][%d] = %4d  REF = %4d  FAIL\n",
                       i, j, C[i][j], REF[i][j]);
            }
        }
    }
    printf("RESULT: %d/%d PASS", passed, total);
    if (passed == total)
        printf("  ==> ALL PASS\n");
    else
        printf("  ==> MISMATCH\n");

    return (passed == total) ? 0 : 1;
}
