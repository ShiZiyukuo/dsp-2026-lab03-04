#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dot.py —— Scaled Dot-Product 的 Python 实现（仅标准库）。

统一接口：dot(a, b) -> float64 标量
读数：读 gen_data.py 生成的裸 float64 小端二进制文件（无文件头）。

两种用法：
  1) 一次性求值（正确性核对用）：
         python dot.py a_10000_f64.bin b_10000_f64.bin
     输出：N=<n> SUM=<17 位有效数字>

  2) 应答式 worker（统一计时协议用，benchmark.py 以同样方式驱动 C/Rust 版本）：
         python dot.py --serve a_10000_f64.bin b_10000_f64.bin
     载入数据后打印 "READY <n>"，然后逐行读命令并应答：
         b        -> 打印 0（空转请求，用于实测管道往返基线 RTT）
         r <k>    -> 连续做 k 次点积，把 k 次结果累加后打印
         q        -> 退出
     每次应答后 flush，外层 benchmark.py 用 perf_counter 包住「写命令 -> 读应答」。

计时口径：本文件不含任何计时逻辑；所有耗时由外层 benchmark.py 的
time.perf_counter() 测量，三语言一致。
"""
import array
import sys

# ---------------------------------------------------------------- 核心接口

def dot(a, b):
    """点积：dot(a, b) = sum(a[i] * b[i])，float64 顺序累加。

    刻意使用显式 for 循环（而不是 sum(generator)），作为「手写基准」，
    与 C / Rust 的 for 循环在累加顺序上完全一致，便于逐位比对。
    """
    n = len(a)
    if n != len(b):
        raise ValueError("length mismatch: %d vs %d" % (n, len(b)))
    s = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s


def dot_fsum(a, b):
    """高精度参考实现（math.fsum，精确求和），只用于正确性核对，不参与计时。"""
    import math
    if len(a) != len(b):
        raise ValueError("length mismatch")
    return math.fsum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------- IO

def load_f64(path):
    """读裸 float64 小端二进制文件 -> array('d')。"""
    arr = array.array("d")
    nbytes = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            nbytes += len(chunk)
            arr.frombytes(chunk)
    if sys.byteorder != "little":
        arr.byteswap()
    if nbytes % 8 != 0:
        raise ValueError("file %s size %d is not a multiple of 8" % (path, nbytes))
    return arr


# ---------------------------------------------------------------- 两种运行模式

def run_once(pa, pb):
    a = load_f64(pa)
    b = load_f64(pb)
    n = len(a)
    if len(b) != n:
        raise ValueError("dimension mismatch: %d vs %d" % (n, len(b)))
    s = dot(a, b)
    sys.stdout.write("N=%d SUM=%.17g\n" % (n, s))
    sys.stdout.flush()


def run_serve(pa, pb):
    a = load_f64(pa)
    b = load_f64(pb)
    n = len(a)
    if len(b) != n:
        raise ValueError("dimension mismatch: %d vs %d" % (n, len(b)))
    out = sys.stdout
    out.write("READY %d\n" % n)
    out.flush()
    for line in sys.stdin:
        cmd = line.strip()
        if not cmd:
            continue
        if cmd == "q":
            break
        elif cmd == "b":
            out.write("0\n")
            out.flush()
        elif cmd.startswith("r "):
            k = int(cmd[2:])
            total = 0.0
            for _ in range(k):
                total += dot(a, b)
            out.write("%.17g\n" % total)
            out.flush()
        else:
            out.write("ERR unknown command\n")
            out.flush()
            break


def main(argv):
    if len(argv) >= 4 and argv[1] == "--serve":
        run_serve(argv[2], argv[3])
    elif len(argv) >= 3:
        run_once(argv[1], argv[2])
    else:
        sys.stderr.write("usage: dot.py [--serve] <a.bin> <b.bin>\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
