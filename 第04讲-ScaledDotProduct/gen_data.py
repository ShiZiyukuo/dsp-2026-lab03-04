#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_data.py —— 生成三语言共用的 float64 小端二进制向量。

固定随机种子，生成 N = 10^4 / 10^5 / 10^6 三组 (a, b) 向量，
每组各存两个文件：a_<N>_f64.bin、b_<N>_f64.bin。

格式：裸 float64 小端（little-endian）数组，无文件头，
      元素个数 n = 文件字节数 / 8。

只用标准库。
"""
import argparse
import array
import os
import random
import sys

SEED = 20261117
SIZES = (10 ** 4, 10 ** 5, 10 ** 6)


def gen_pair(n, seed):
    """生成一对 [-1, 1) 均匀分布的 float64 向量。"""
    rng = random.Random(seed)
    a = array.array("d", (rng.uniform(-1.0, 1.0) for _ in range(n)))
    b = array.array("d", (rng.uniform(-1.0, 1.0) for _ in range(n)))
    return a, b


def write_f64_le(path, arr):
    """按小端顺序写裸 float64 数组。"""
    if sys.byteorder != "little":      # x86/ARM 上通常是小端，仍显式保证
        arr = array.array("d", arr)
        arr.byteswap()
    with open(path, "wb") as f:
        arr.tofile(f)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser(description="generate float64 LE vectors for dot-product bench")
    ap.add_argument("--out", default=None, help="输出目录（默认 <script>/../data）")
    ap.add_argument("--sizes", default="", help="逗号分隔的 N 列表，默认 1e4,1e5,1e6")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(here, "..", "data")
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)

    sizes = [int(s) for s in args.sizes.split(",")] if args.sizes else list(SIZES)

    print("seed = %d" % args.seed)
    print("out  = %s" % out)
    print("%-9s %-24s %-24s %10s %10s" % ("N", "file_a", "file_b", "bytes_a", "bytes_b"))
    for i, n in enumerate(sizes):
        # 每个 N 用不同的种子流，但整体可复现
        a, b = gen_pair(n, args.seed + i)
        pa = os.path.join(out, "a_%d_f64.bin" % n)
        pb = os.path.join(out, "b_%d_f64.bin" % n)
        sa = write_f64_le(pa, a)
        sb = write_f64_le(pb, b)
        print("%-9d %-24s %-24s %10d %10d" % (n, os.path.basename(pa),
                                             os.path.basename(pb), sa, sb))
    print("done.")


if __name__ == "__main__":
    main()
