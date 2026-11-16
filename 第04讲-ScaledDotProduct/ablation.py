#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ablation.py —— 对照实验：把「编译参数」和「结果是否被消费」各当一次自变量。

四组真实对照（同一份数据、同一台机器、同一套应答式计时协议）：
  A. C 版 /Od vs /O2        ：-O2/-Od 带来的差距（MSVC 无 gcc，/Od≈-O0、/O2≈-O2）
  B. Rust -C opt-level=0 vs 3（debug vs release）：是否真的必须 release
  C. C 版「结果被丢弃」/O2  ：编译器是否把整个点积循环删掉（dumpbin 直接看指令）
  D. 整进程计时 vs 应答式    ：把进程启动 + 读文件算进计时会发生什么

本机工具链：MSVC cl 19.44（本机无 gcc，WinLibs 下载中断）、rustc 1.100.0 (msvc host)。
两者都需要 vcvars64 环境里的链接器，所以统一通过 cmd + vcvars 调用。

用法：
    python code/ablation.py
输出：
    logs/ablation.txt（stdout 由外部 tee）/ logs/ablation.json
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
import benchmark as bm   # 复用同一套应答式计时协议

VCVARS = r'"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"'
RUSTC = r"C:\Users\LZX\.cargo\bin\rustc.exe"


def vs_run(inner, timeout=300):
    """在 vcvars64 环境里执行一条命令，返回 CompletedProcess。"""
    cmd = 'call %s >nul 2>&1 && %s' % (VCVARS, inner)
    print("$ " + inner)
    cp = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                        cwd=ROOT, timeout=timeout)
    out = (cp.stdout or "") + (cp.stderr or "")
    if out.strip():
        print(out.rstrip()[:1200])
    return cp


def main():
    os.makedirs(BUILD, exist_ok=True)
    out = {"groups": {}}

    print("=" * 78)
    print("A) C：cl /Od vs cl /O2")
    print("=" * 78)
    variants = {}
    for opt, tag in (("/Od", "Od"), ("/O2", "O2")):
        exe = os.path.join(BUILD, "dot_c_%s.exe" % tag)
        cp = vs_run('cl /nologo %s /Fe:"%s" "%s"' % (opt, exe, os.path.join(HERE, "dot.c")))
        if os.path.exists(exe):
            variants["C " + opt] = [exe]

    print("\n" + "=" * 78)
    print("B) Rust：-C opt-level=0（debug）vs -C opt-level=3（release）")
    print("=" * 78)
    for lvl in ("0", "3"):
        exe = os.path.join(BUILD, "dot_rs_opt%s.exe" % lvl)
        vs_run('"%s" --edition 2021 -C opt-level=%s -o "%s" "%s"'
               % (RUSTC, lvl, exe, os.path.join(HERE, "dot.rs")))
        if os.path.exists(exe):
            variants["Rust opt=%s" % lvl] = [exe]

    res = {}
    print("\n" + "=" * 78)
    print("同一套应答式协议下的对照（预热 3 轮 + 正式 10 轮取中位数）")
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

    if res.get(1000000) and "C /Od" in res[1000000] and "C /O2" in res[1000000]:
        r = res[1000000]["C /Od"]["median"] / res[1000000]["C /O2"]["median"]
        print("\n  => N=10^6 时 C /Od ÷ /O2 = %.2fx" % r)
        out["groups"]["c_O0_over_O2_1e6"] = r
    if res.get(1000000) and "Rust opt=0" in res[1000000] and "Rust opt=3" in res[1000000]:
        r = res[1000000]["Rust opt=0"]["median"] / res[1000000]["Rust opt=3"]["median"]
        print("  => N=10^6 时 Rust debug ÷ release = %.2fx" % r)
        out["groups"]["rust_debug_over_release_1e6"] = r

    # ---------------- C) 结果被丢弃：直接看机器码
    print("\n" + "=" * 78)
    print("C) C 版「结果被丢弃」：/O2 是否删掉了整个点积循环（dumpbin 看指令）")
    print("=" * 78)
    noconsume = os.path.join(BUILD, "dot_c_noconsume.exe")
    out["groups"]["noconsume"] = {}
    for label, exe in (("正确版 dot_c.exe", os.path.join(BUILD, "dot_c.exe")),
                       ("反例 dot_c_noconsume.exe", noconsume)):
        if not os.path.exists(exe):
            continue
        cp = vs_run('dumpbin /disasm "%s"' % exe, timeout=300)
        text = (cp.stdout or "") + (cp.stderr or "")
        nmul = len(re.findall(r"\bmulsd\b", text, re.I))
        nadd = len(re.findall(r"\baddsd\b", text, re.I))
        nmulps = len(re.findall(r"\bmulpd\b", text, re.I))
        naddps = len(re.findall(r"\baddpd\b", text, re.I))
        print("  %-28s mulsd=%-4d addsd=%-4d mulpd=%-4d addpd=%d"
              % (label, nmul, nadd, nmulps, naddps))
        out["groups"]["noconsume"][label] = {"mulsd": nmul, "addsd": nadd,
                                             "mulpd": nmulps, "addpd": naddps,
                                             "size": os.path.getsize(exe)}
    if os.path.exists(noconsume):
        pa = os.path.join(ROOT, "data", "a_1000000_f64.bin")
        pb = os.path.join(ROOT, "data", "b_1000000_f64.bin")
        vals = []
        for _ in range(5):
            t0 = time.perf_counter()
            subprocess.run([noconsume, pa, pb], capture_output=True)
            vals.append(time.perf_counter() - t0)
        med = bm.median(vals)
        print("  反例程序整进程耗时中位数 = %s（只剩进程启动 + 读 16MB 文件）" % bm.fmt_time(med))
        out["groups"]["noconsume"]["whole_process_1e6"] = med

    # ---------------- D) 整进程计时 vs 应答式协议
    print("\n" + "=" * 78)
    print("D) 计时口径对比：整进程计时（含启动+读文件） vs 应答式协议（只计计算）")
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
                subprocess.run([cexe, pa, pb], capture_output=True)
                vals.append(time.perf_counter() - t0)
            naive[n] = bm.median(vals)
            m = bm.measure_worker([cexe], n, warmup=3, rounds=10)
            proto[n] = m["median"]
            print("  N=%-8d 整进程=%-12s 应答式=%-12s 虚高 %.1f 倍"
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
