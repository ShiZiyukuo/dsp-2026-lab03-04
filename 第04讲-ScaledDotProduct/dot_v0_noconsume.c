/* dot_v0_noconsume.c —— 「初版草稿」的反例，故意不消费结果。
 *
 * 用来复现真实踩过的坑：算完点积却把结果丢掉（没有 printf / 没有累加到任何
 * 会被输出的变量），gcc -O2 会认定整段循环无副作用并**直接删除**，
 * 于是「C 快到测不出来」——但这是假数据，不是性能。
 *
 * 编译：
 *     gcc -O2 -o build/dot_c_noconsume.exe code/dot_v0_noconsume.c
 * 与正确版对比：
 *     objdump -d build/dot_c_noconsume.exe | findstr /c:"mulsd" /c:"addsd"
 *     objdump -d build/dot_c.exe           | findstr /c:"mulsd" /c:"addsd"
 * 正确版有 mulsd/addsd 指令，反例版里一条都没有。
 */
#include <stdio.h>
#include <stdlib.h>

static double dot(const double *a, const double *b, size_t n)
{
    double s = 0.0;
    for (size_t i = 0; i < n; i++) {
        s += a[i] * b[i];
    }
    return s;                      /* 返回值没人用 */
}

static double *load_f64(const char *path, size_t *out_n)
{
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "ERR cannot open %s\n", path); return NULL; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    rewind(f);
    if (sz < 0 || (sz % 8) != 0) { fclose(f); return NULL; }
    size_t n = (size_t)sz / 8;
    double *p = (double *)malloc(n ? n * sizeof(double) : sizeof(double));
    if (n && fread(p, sizeof(double), n, f) != n) { free(p); fclose(f); return NULL; }
    fclose(f);
    *out_n = n;
    return p;
}

int main(int argc, char **argv)
{
    if (argc < 3) return 2;
    size_t na = 0, nb = 0;
    double *a = load_f64(argv[1], &na);
    double *b = load_f64(argv[2], &nb);
    if (!a || !b) return 1;
    double s = dot(a, b, na);      /* 结果被丢弃 —— -O2 会把 dot 整个优化掉 */
    printf("N=%zu SUM=<未打印，结果被丢弃>\n", na);   /* 注意：没有打印 s */
    (void)s;
    free(a); free(b);
    return 0;
}
