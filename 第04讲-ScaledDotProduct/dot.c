/* dot.c —— Scaled Dot-Product 的 C 实现（仅标准库）
 *
 * 统一接口：double dot(const double *a, const double *b, size_t n)
 * 读数：读 gen_data.py 生成的裸 float64 小端二进制文件（无文件头）。
 *
 * 编译（务必 -O2）：
 *     gcc -O2 -o build/dot_c.exe code/dot.c
 *
 * 用法：
 *     dot_c.exe a_10000_f64.bin b_10000_f64.bin            # 一次性求值
 *     dot_c.exe --serve a_10000_f64.bin b_10000_f64.bin    # 应答式 worker
 *
 * 应答协议与 dot.py --serve 完全一致：
 *     启动后打印 "READY <n>"；命令 b / r <k> / q；每次应答后 fflush。
 *
 * 两个防优化措施（缺一不可，否则 -O2 会直接删掉整段循环）：
 *   1) 结果必须被消费：一次性模式 printf 出来；worker 模式累加到 total 再打印。
 *   2) dot 加 noinline：避免 -O2 把点积内联进重复 k 次的循环后做循环不变量外提，
 *      导致「k 次点积」被折叠成 1 次（看起来快 k 倍，实际是假数据）。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_MSC_VER)
#define DOT_NOINLINE __declspec(noinline)
#else
#define DOT_NOINLINE __attribute__((noinline))
#endif

/* 核心接口：顺序累加，与 Python / Rust 版顺序一致 */
DOT_NOINLINE
static double dot(const double *a, const double *b, size_t n)
{
    double s = 0.0;
    for (size_t i = 0; i < n; i++) {
        s += a[i] * b[i];
    }
    return s;
}

/* 读裸 float64 小端文件：返回元素个数，失败返回 (size_t)-1 */
static double *load_f64(const char *path, size_t *out_n)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "ERR cannot open %s\n", path);
        return NULL;
    }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long sz = ftell(f);
    if (sz < 0 || (sz % 8) != 0) {
        fprintf(stderr, "ERR bad size %ld for %s\n", sz, path);
        fclose(f);
        return NULL;
    }
    rewind(f);
    size_t n = (size_t)sz / 8;
    double *p = (double *)malloc(n ? n * sizeof(double) : sizeof(double));
    if (!p) { fclose(f); return NULL; }
    if (n && fread(p, sizeof(double), n, f) != n) {
        fprintf(stderr, "ERR short read on %s\n", path);
        free(p);
        fclose(f);
        return NULL;
    }
    fclose(f);
    *out_n = n;
    return p;
}

static int run_once(const char *pa, const char *pb)
{
    size_t na = 0, nb = 0;
    double *a = load_f64(pa, &na);
    double *b = load_f64(pb, &nb);
    if (!a || !b) return 1;
    if (na != nb) {
        fprintf(stderr, "ERR dimension mismatch: %zu vs %zu\n", na, nb);
        return 1;
    }
    double s = dot(a, b, na);
    printf("N=%zu SUM=%.17g\n", na, s);
    fflush(stdout);
    free(a); free(b);
    return 0;
}

static int run_serve(const char *pa, const char *pb)
{
    size_t na = 0, nb = 0;
    double *a = load_f64(pa, &na);
    double *b = load_f64(pb, &nb);
    if (!a || !b) return 1;
    if (na != nb) {
        fprintf(stderr, "ERR dimension mismatch\n");
        return 1;
    }
    printf("READY %zu\n", na);
    fflush(stdout);

    char line[256];
    while (fgets(line, sizeof(line), stdin)) {
        if (line[0] == 'q') break;
        if (line[0] == 'b') {
            printf("0\n");
            fflush(stdout);
        } else if (line[0] == 'r') {
            long k = strtol(line + 1, NULL, 10);
            if (k < 0) k = 0;
            double total = 0.0;
            for (long i = 0; i < k; i++) {
                total += dot(a, b, na);
            }
            printf("%.17g\n", total);
            fflush(stdout);
        } else {
            printf("ERR unknown command\n");
            fflush(stdout);
            break;
        }
    }
    free(a); free(b);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc >= 4 && strcmp(argv[1], "--serve") == 0) {
        return run_serve(argv[2], argv[3]);
    }
    if (argc >= 3) {
        return run_once(argv[1], argv[2]);
    }
    fprintf(stderr, "usage: dot_c [--serve] <a.bin> <b.bin>\n");
    return 2;
}
