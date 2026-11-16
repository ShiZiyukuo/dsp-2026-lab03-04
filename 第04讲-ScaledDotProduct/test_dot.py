#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_dot.py —— 点积实现的 5 个边界用例（只用标准库）。

覆盖指南要求的 5 个边界：
    1) n = 0          空向量：结果必须是 0.0，不能崩、不能读到脏数据
    2) n = 1          单元素：结果必须精确等于 a[0]*b[0]
    3) 整数精确值     小整数点积可被 float64 精确表示：结果必须逐位相等
    4) 全零向量       0 * x 累加：结果必须是 +0.0
    5) 极大极小混合   1e308 / 1e-300 同场，检查是否溢出/下溢/NaN，
                      以及顺序累加与 fsum 参考一致

对每个用例：
    - 先用 Python 的 dot() 断言（含与 math.fsum 参考的比较）；
    - 再把向量写成临时裸 float64 小端 bin 文件，交给 C / Rust 可执行文件
      用同样的一次性模式算一遍，断言三语言结果一致（相对误差 <= 1e-9）。
      这样「边界维度未校验」这个隐患就被真正堵住了，而不是只测了 Python。

用法：
    python test_dot.py
退出码 0 = 全部 PASS。
"""
import array
import math
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
sys.path.insert(0, HERE)

import dot as dotmod  # noqa: E402

SUM_RE = re.compile(r"N=(\d+)\s+SUM=(\S+)")

PASS = 0
FAIL = 0


def write_f64_le(path, vals):
    arr = array.array("d", vals)
    if sys.byteorder != "little":
        arr.byteswap()
    with open(path, "wb") as f:
        arr.tofile(f)


def run_exe(cmd_prefix, pa, pb):
    cp = subprocess.run(cmd_prefix + [pa, pb], capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError("exited %d: %s" % (cp.returncode, cp.stderr))
    m = SUM_RE.search(cp.stdout)
    if not m:
        raise RuntimeError("cannot parse %r" % cp.stdout)
    return int(m.group(1)), float(m.group(2))


def close(a, b, tol=1e-9):
    if a == b:
        return True
    denom = max(abs(a), abs(b), 1e-300)
    return abs(a - b) / denom <= tol


def check_case(name, av, bv, expect, note=""):
    """一个用例：先断言 Python，再断言三语言一致。"""
    global PASS, FAIL
    a = array.array("d", av)
    b = array.array("d", bv)
    detail = []

    def ok(cond, msg):
        if not cond:
            raise AssertionError(msg)

    try:
        # --- 1) Python 实现
        got = dotmod.dot(a, b)
        ok(not math.isnan(got), "Python 结果出现 NaN")
        if expect is not None:
            ok(got == expect, "Python 结果 %r != 期望 %r" % (got, expect))
        fsum = dotmod.dot_fsum(a, b)
        ok(close(got, fsum), "Python 与 fsum 参考差太多: %r vs %r" % (got, fsum))
        # 空向量 / 全零的特殊符号检查
        if len(av) == 0 or all(x == 0.0 for x in av) or all(x == 0.0 for x in bv):
            ok(got == 0.0 and math.copysign(1.0, got) == 1.0,
               "应得 +0.0，实得 %r" % got)
        detail.append("Python=%r" % got)

        # --- 2) C / Rust 交叉验证（写临时 bin，三语言读同一份文件）
        with tempfile.TemporaryDirectory(prefix="dot_test_") as td:
            pa = os.path.join(td, "a.bin")
            pb = os.path.join(td, "b.bin")
            write_f64_le(pa, a)
            write_f64_le(pb, b)
            for lang, exe in (("C", os.path.join(BUILD, "dot_c.exe")),
                              ("Rust", os.path.join(BUILD, "dot_rs.exe"))):
                if not os.path.exists(exe):
                    detail.append("%s=SKIP(未编译)" % lang)
                    continue
                n, val = run_exe([exe], pa, pb)
                ok(n == len(a), "%s 读到的 n=%d != %d" % (lang, n, len(a)))
                ok(not math.isnan(val), "%s 结果出现 NaN" % lang)
                ok(close(val, got), "%s 结果 %r 与 Python %r 不一致" % (lang, val, got))
                detail.append("%s=%r" % (lang, val))

        PASS += 1
        print("PASS  %-22s %s %s" % (name, " ".join(detail), note))
    except AssertionError as e:
        FAIL += 1
        print("FAIL  %-22s %s" % (name, e))
    except Exception as e:                       # noqa: BLE001
        FAIL += 1
        print("FAIL  %-22s 异常: %s" % (name, e))


def main():
    print("=" * 78)
    print("点积边界用例（Python 断言 + C/Rust 三语言交叉验证）")
    print("=" * 78)

    # 1) n = 0
    check_case("n=0 空向量", [], [], 0.0, "长度不匹配/空文件也不能崩")
    # 2) n = 1
    a0, b0 = 0.1, 3.0
    check_case("n=1 单元素", [a0], [b0], a0 * b0)
    # 3) 整数精确值 [1,2,3]·[4,5,6] = 32
    check_case("整数精确值 1..3·4..6", [1.0, 2.0, 3.0], [4.0, 5.0, 6.0], 32.0)
    # 4) 全零向量
    check_case("全零向量", [0.0] * 1000, [1.5] * 1000, 0.0,
               "必须是 +0.0，不能是 -0.0/NaN")
    # 5) 极大极小混合
    av = [1e308, -1e308, 1e-300, 3.0]
    bv = [1.0, 1.0, 1e300, 4.0]
    check_case("极大极小混合 1e308/1e-300", av, bv, 13.0,
               "1e308-1e308 抵消后剩 1+12")

    # 附：长度不匹配必须报错（而不是悄悄算 min 长度）——额外一条，不计入 5 个用例
    try:
        dotmod.dot(array.array("d", [1.0, 2.0]), array.array("d", [1.0]))
        print("FAIL  长度不匹配未报错")
        global FAIL
        FAIL += 1
    except ValueError as e:
        print("PASS  长度不匹配正确报错    ValueError: %s" % e)

    print("=" * 78)
    print("5 个边界用例结果：%d PASS / %d FAIL" % (PASS, FAIL))
    print("=" * 78)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
