/*
 * bench_matmul.c —— -O0 与 -O2 的**真实耗时**对比（辅助文件，非四层交付源码之一）
 *
 * 3x3 太小，单次乘法纳秒级，进程启动时间会淹没一切，
 * 所以这里把同一个三重循环跑 REPEAT 次，用 clock() 测 CPU 时间。
 * 每一轮把结果累加进 volatile 全局变量，防止编译器把整个循环优化掉。
 *
 * 编译：cl /Od /utf-8 /Feben_O0.exe bench_matmul.c
 *       cl /O2 /utf-8 /Feben_O2.exe bench_matmul.c
 */
#include <stdio.h>
#include <time.h>

#define N 3
#define REPEAT 20000000L   /* 2000 万轮 3x3 乘加：27 次乘加/轮 */

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

volatile long g_sink;   /* 阻止死代码消除 */

int main(void)
{
    int C[N][N];
    int i, j, k;
    long r;
    long checksum = 0;
    clock_t t0, t1;
    double sec;

    t0 = clock();
    for (r = 0; r < REPEAT; r++) {
        for (i = 0; i < N; i++) {
            for (j = 0; j < N; j++) {
                C[i][j] = 0;
                for (k = 0; k < N; k++) {
                    C[i][j] += A[i][k] * B[k][j];
                }
            }
        }
        g_sink = C[r % N][r % N];
    }
    t1 = clock();

    sec = (double)(t1 - t0) / CLOCKS_PER_SEC;

    for (i = 0; i < N; i++)
        for (j = 0; j < N; j++)
            checksum = C[i][j];

    printf("REPEAT = %ld 轮 x 9 元素 = %ld 次 C[i][j] 计算\n",
           REPEAT, REPEAT * 9);
    printf("CHECKSUM = %ld\n", checksum);
    printf("CPU_TIME = %.4f s\n", sec);
    printf("PER_ITER = %.3f ns\n", sec * 1e9 / (double)REPEAT);
    return 0;
}
