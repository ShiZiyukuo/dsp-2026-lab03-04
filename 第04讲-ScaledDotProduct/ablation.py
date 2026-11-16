#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ablation.py —— 消融/对照实验：把「编译参数」和「结果是否被消费」各当一次自变量。

四组真实对照（同一份数据、同一台机器、同一套「请求—应答」计时协议）：
  A. C 版 gcc -O0 vs gcc -O2     ：-O2 带来多少倍
  B. Rust opt-level=0 vs 3       ：是否真的必须 release
  C. C 版「结果被丢弃」+ gcc -O2 ：objdump 看浮点指令是否还在（是否被整段抹掉）
  D. 整进程计时 vs 请求—应答计时  ：把启动 + 读盘算进去会发生什么

工具链：gcc 16.2.0（MSYS2 mingw-w64，需 mingw64\bin 在 PATH）、rustc 1.100.0（msvc host，
链接需要 vcvars64 环境里的 link.exe）。gcc 编出来的 exe 运行时同样依赖 mingw64\bin 的 DLL。

用法：python code/ablation.py
输出：logs/ablation.json（stdout 由外部 tee 成 logs/ablation.txt）
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, "build")
LOGS = os.path.join(ROOT, "logs")
sys.path.insert(0, HERE)
import benchmark as bm   # 复用同一套请求—应答计时协议

MINGW_BIN = r"D:\DeepSeek-Harness\hw-0304\tools\msys64\mingw64\bin"
GCC = os.path.join(MINGW_BIN, "gcc.exe")
OBJDUMP = os.path.join(MINGW_BIN, "objdump.exe")
VCVARS = r'"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"'
RUSTC = r"C:\Users\LZX\.cargo\bin\rustc.exe"

ENV = dict(os.environ)
ENV["PATH"] = MINGW_BIN + os.pathsep + ENV.get("PATH", "")


def run(cmd, shell=False, env=None, timeout=300):
    print("$ " + (cmd if shell else " ".join(cmd)))
    cp = subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                        cwd=ROOT, env=env or ENV, timeout=timeout)
    out = (cp.stdout or "") + (cp.stderr or "")
    if out.strip():
        print(out.rstrip()[:600])
    return cp


def count_insn(objdump_exe, exe_path, dump_path):
    cp = run([objdump_exe, "-d", exe_path], timeout=300)
    text = (cp.stdout or "") + (cp.stderr or "")
    try:
        with open(dump_path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    cnt = {}
    for key in ("mulsd", "addsd", "mulpd", "addpd", "vfmadd", "vmulpd", "vaddpd"):
        cnt[key] = len(re.findall(r"\b%s\w*\b" % key, text, re.I))
    return cnt


def main():
    os.makedirs(BUILD, exist_ok=True)
    out = {"groups": {}, "compilers": {}}
    print("=" * 78)
    print("A) C：gcc -O0 vs gcc -O2")
    print("=" * 78)
    variants = {}
    v = run([GCC, "--version"])
    out["compilers"]["gcc"] = (v.stdout or "").splitlines()[0] if v.stdout else ""
    print("gcc:", out["compilers"]["gcc"])
    for opt, tag in (("-O0", "O0"), ("-O2", "O2")):
        exe = os.path.join(BUILD, "dot_c_%s.exe" % tag)
        run([GCC, opt, "-o", exe, os.path.join(HERE, "dot.c")])
        if os.path.exists(exe):
            variants["C gcc %s" % opt] = [exe]

    print("\n" + "=" * 78)
    print("B) Rust：-C opt-level=0（debug）vs -C opt-level=3（release）")
    print("=" * 78)
    rv = run([RUSTC, "--version"])
    out["compilers"]["rustc"] = (rv.stdout or "").strip()
    print("rustc:", out["compilers"]["rustc"])
    for lvl in ("0", "3"):
        exe = os.path.join(BUILD, "dot_rs_opt%s.exe" % lvl)
        inner = '"%s" --edition 2021 -C opt-level=%s -o "%s" "%s"' % (
            RUSTC, lvl, exe, os.path.join(HERE, "dot.rs"))
        run('call %s >nul 2>&1 && %s' % (VCVARS, inner), shell=True)
        if os.path.exists(exe):
            variants["Rust opt=%s" % lvl] = [exe]

    res = {}
    print("\n" + "=" * 78)
    print("同一套「请求—应答」协议下的对照（热身 3 次 + 正式 10 轮取中位数）")
    print("=" * 78)
    for n in (10000, 1000000):
        res[n] = {}
        for name, cmd in variants.items():
            try:
                m = bm.measure_worker(cmd, n, warmup=3, rounds=10)
                res[n][name] = {"median": m["median"], "min": m["min"],
                                "k": m["k"], "rtt_us": m["rtt_us"]}
                print("  N=%-8d %-14s median=%-12s min=%-12s k=%d"
                      % (n, name, bm.fmt_time(m["median"]), bm.fmt_time(m["min"]), m["k"]))
            except Exception as e:                # noqa: BLE001
                print("  N=%-8d %-14s 失败: %s" % (n, name, e))
    out["groups"]["opt_levels"] = res

    if res.get(1000000) and "C gcc -O0" in res[1000000] and "C gcc -O2" in res[1000000]:
        r = res[1000000]["C gcc -O0"]["median"] / res[1000000]["C gcc -O2"]["median"]
        print("\n  => N=10^6 时 C -O0 ÷ -O2 = %.2fx" % r)
        out["groups"]["c_O0_over_O2_1e6"] = r
    if res.get(1000000) and "Rust opt=0" in res[1000000] and "Rust opt=3" in res[1000000]:
        r = res[1000000]["Rust opt=0"]["median"] / res[1000000]["Rust opt=3"]["median"]
        print("  => N=10^6 时 Rust debug ÷ release = %.2fx" % r)
        out["groups"]["rust_debug_over_release_1e6"] = r

    # ---------------- C) 结果被丢弃：看机器码
    print("\n" + "=" * 78)
    print("C) C 版「结果被丢弃」：gcc -O2 是否把整段计算抹掉（objdump 数浮点指令）")
    print("=" * 78)
    noconsume = os.path.join(BUILD, "dot_c_noconsume.exe")
    if not os.path.exists(noconsume):
        run([GCC, "-O2", "-o", noconsume, os.path.join(HERE, "dot_v0_noconsume.c")])
    out["groups"]["noconsume"] = {}
    for label, exe in (("正确版 dot_c.exe", os.path.join(BUILD, "dot_c.exe")),
                       ("反例 dot_c_noconsume.exe", noconsume)):
        if not os.path.exists(exe):
            continue
        cnt = count_insn(OBJDUMP, exe, os.path.join(BUILD, os.path.basename(exe) + ".disasm.txt"))
        print("  %-28s mulsd=%-3d addsd=%-3d mulpd=%-2d addpd=%-2d size=%d"
              % (label, cnt["mulsd"], cnt["addsd"], cnt["mulpd"], cnt["addpd"],
                 os.path.getsize(exe)))
        cnt["size"] = os.path.getsize(exe)
        out["groups"]["noconsume"][label] = cnt
    if os.path.exists(noconsume):
        pa = os.path.join(ROOT, "data", "a_1000000_f64.bin")
        pb = os.path.join(ROOT, "data", "b_1000000_f64.bin")
        vals = []
        for _ in range(5):
            t0 = time.perf_counter()
            subprocess.run([noconsume, pa, pb], capture_output=True, env=ENV)
            vals.append(time.perf_counter() - t0)
        med = bm.median(vals)
        print("  反例程序整进程耗时中位数 = %s（只剩进程启动 + 读 16 MB 文件）" % bm.fmt_time(med))
        out["groups"]["noconsume"]["whole_process_1e6"] = med

    # ---------------- D) 整进程计时 vs 请求—应答
    print("\n" + "=" * 78)
    print("D) 计时口径对比：整进程计时（含启动+读盘） vs 请求—应答（只计计算）")
    print("=" * 78)
    cexe = os.path.join(BUILD, "dot_c.exe")
    naive, proto = {}, {}
    if os.path.exists(cexe):
        for n in (10000, 1000000):
            pa = os.path.join(ROOT, "data", "a_%d_f64.bin" % n)
            pb = os.path.join(ROOT, "data", "b_%d_f64.bin" % n)
            vals = []
            for _ in range(5):
                t0 = time.perf_counter()
                subprocess.run([cexe, pa, pb], capture_output=True, env=ENV)
                vals.append(time.perf_counter() - t0)
            naive[n] = bm.median(vals)
            m = bm.measure_worker([cexe], n, warmup=3, rounds=10)
            proto[n] = m["median"]
            print("  N=%-8d 整进程=%-12s 请求—应答=%-12s 虚高 %.1f 倍"
                  % (n, bm.fmt_time(naive[n]), bm.fmt_time(proto[n]),
                     naive[n] / proto[n]))
    out["groups"]["timing_protocol"] = {"naive": naive, "protocol": proto}

    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, "ablation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n写入 logs/ablation.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
