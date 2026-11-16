#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""benchmark.py —— 三语言统一点积基准测试（仅标准库）。

计时协议（三语言完全一致，计时统一由本文件的 time.perf_counter() 完成）
--------------------------------------------------------------------------
C / Rust 是编译型语言，若按「启动进程 -> 跑完 -> 进程退出」整体计时，
进程启动（Windows 上 10~30 ms）和 8 MB 文件读取会完全淹没真正的计算
（N=10^4 时 C 的点积只有几微秒），必然得出「三语言一样快」的错误结论。
因此三版程序都实现了同一套「请求-应答 worker」协议：

    启动：载入 bin 文件 -> 打印 "READY <n>" -> 阻塞读 stdin
    命令 b        -> 立即回 "0"（空转，用来实测管道往返基线 RTT）
    命令 r <k>    -> 连续算 k 次 dot，把结果累加后回一行
    命令 q        -> 退出

被测时间 = perf_counter 包住「写入命令 -> 读到应答」的整段，再减去同进程内
实测的 RTT，并除以重复次数 k：

    单次 dot 耗时 = (t_round - t_rtt) / k

- t_rtt 用 8 次 ping 的中位数，抵消管道/调度抖动；
- k 由一次标定请求自动调整，让每次计时区间约 80 ms，
  使 RTT 误差占比 < 0.1%（N=10^4 的 C 版若不做这一步，误差会 > 200%）；
- 预热 3 轮后正式计 10 轮，取中位数与最小值；
- 每种语言在每个规模上独立跑 5 轮（新进程、重新读盘），取 5 个中位数的中位数。

正确性核对：三语言 one-shot 模式各算一次，与 Python 基准及 math.fsum 高精度参考
比对相对误差，要求 <= 1e-9。

用法：
    python benchmark.py              # 正式跑：3 规模 x 3 语言 x 5 次运行
    python benchmark.py --runs 2 --rounds 5      # 快速调试
    python benchmark.py --naive-demo            # 反例：把进程启动+读文件算进计时
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # lab04/
CODE = os.path.join(ROOT, "code")
DATA = os.path.join(ROOT, "data")
LOGS = os.path.join(ROOT, "logs")
BUILD = os.path.join(ROOT, "build")

PY_EXE = sys.executable
SIZES = (10000, 100000, 1000000)

TARGET_SEC = 0.08          # 每次计时请求的目标时长
PINGS = 8


def build_languages():
    """返回 {语言名: 启动命令前缀（不含 --serve 与路径）}"""
    langs = {"Python": [PY_EXE, os.path.join(CODE, "dot.py")]}
    exe_c = os.path.join(BUILD, "dot_c.exe")
    exe_rs = os.path.join(BUILD, "dot_rs.exe")
    if os.path.exists(exe_c):
        langs["C"] = [exe_c]
    if os.path.exists(exe_rs):
        langs["Rust"] = [exe_rs]
    return langs


# ---------------------------------------------------------------- 一次性求值（正确性）

SUM_RE = re.compile(r"N=(\d+)\s+SUM=(\S+)")


def run_once(cmd_prefix, n, timeout=120):
    pa = os.path.join(DATA, "a_%d_f64.bin" % n)
    pb = os.path.join(DATA, "b_%d_f64.bin" % n)
    cp = subprocess.run(cmd_prefix + [pa, pb], capture_output=True, text=True,
                        timeout=timeout)
    if cp.returncode != 0:
        raise RuntimeError("%s exited %d: %s" % (cmd_prefix, cp.returncode, cp.stderr))
    m = SUM_RE.search(cp.stdout)
    if not m:
        raise RuntimeError("cannot parse output: %r" % cp.stdout[:200])
    return int(m.group(1)), float(m.group(2)), cp.stdout.strip()


def python_reference(n):
    """Python 基准 + math.fsum 高精度参考（只用标准库，直接在本进程算）"""
    sys.path.insert(0, CODE)
    import array
    import dot as dotmod
    pa = os.path.join(DATA, "a_%d_f64.bin" % n)
    pb = os.path.join(DATA, "b_%d_f64.bin" % n)
    a = dotmod.load_f64(pa)
    b = dotmod.load_f64(pb)
    return dotmod.dot(a, b), dotmod.dot_fsum(a, b)


# ---------------------------------------------------------------- 应答式计时

class Worker(object):
    def __init__(self, cmd_prefix, n):
        pa = os.path.join(DATA, "a_%d_f64.bin" % n)
        pb = os.path.join(DATA, "b_%d_f64.bin" % n)
        self.proc = subprocess.Popen(cmd_prefix + ["--serve", pa, pb],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True, bufsize=1)
        line = self.proc.stdout.readline()
        if not line.startswith("READY"):
            raise RuntimeError("worker failed to start: %r / %r"
                               % (line, self.proc.stderr.read(500)))
        self.n = int(line.split()[1])

    def request(self, cmd):
        t0 = time.perf_counter()
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        t1 = time.perf_counter()
        if not line:
            raise RuntimeError("worker died on %r (stderr=%r)"
                               % (cmd, self.proc.stderr.read(500)))
        return t1 - t0, line.strip()

    def ping_rtt(self, k=PINGS):
        vals = [self.request("b")[0] for _ in range(k)]
        return median(vals)

    def close(self):
        try:
            self.proc.stdin.write("q\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 == 1 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def measure_worker(cmd_prefix, n, warmup, rounds, target=TARGET_SEC, verbose=False):
    """一次独立运行：返回单次 dot 耗时的中位数/最小值等。"""
    w = Worker(cmd_prefix, n)
    try:
        rtt = w.ping_rtt()
        # 标定：先测一次 r=1 的往返，估算单次 dot 耗时，用来定重复次数 k
        t_round, s1 = w.request("r 1")
        work = max(t_round - rtt, 1e-9)
        k = int(round(target / work))
        k = max(1, min(k, 200000))
        # 用 k 次请求重新标定一次（k 次的总量也可能受缓存影响）
        t_round_k, s_k = w.request("r %d" % k)
        work_k = max(t_round_k - rtt, 1e-9) / k
        k = max(1, min(int(round(target / work_k)), 200000))
        # 预热
        for _ in range(warmup):
            w.request("r %d" % k)
        # 正式计时
        rtt2 = w.ping_rtt()
        samples = []
        sums = set()
        for _ in range(rounds):
            t_round, line = w.request("r %d" % k)
            samples.append(max(t_round - rtt2, 1e-9) / k)
            sums.add(line)
        if len(sums) != 1:
            raise RuntimeError("报时期间校验和不稳定: %r" % sums)
        return {
            "n": n, "k": k, "rtt_us": rtt2 * 1e6,
            "median": median(samples), "min": min(samples), "max": max(samples),
            "samples": samples, "sum_k": float(sums.pop()),
        }
    finally:
        w.close()


# ---------------------------------------------------------------- 输出

def fmt_time(sec):
    if sec >= 1.0:
        return "%.3f s" % sec
    if sec >= 1e-3:
        return "%.3f ms" % (sec * 1e3)
    return "%.3f us" % (sec * 1e6)


def print_table(sizes, langs, result):
    w = 16
    print()
    print("=" * 84)
    print("耗时对比表：单次 dot(a,b) 中位耗时（预热 3 轮 + 正式 10 轮，5 次独立运行取中位数）")
    print("=" * 84)
    header = "%-9s" % "N" + "".join("%-*s" % (w, name) for name in langs) \
             + "%12s" % "C/Python" + "%12s" % "Rust/Python"
    print(header)
    print("-" * 84)
    for n in sizes:
        row = "%-9d" % n
        base = result[n]["Python"]["median"]
        for name in langs:
            row += "%-*s" % (w, fmt_time(result[n][name]["median"]))
        sp_c = base / result[n]["C"]["median"] if "C" in langs else float("nan")
        sp_r = base / result[n]["Rust"]["median"] if "Rust" in langs else float("nan")
        row += "%11.2fx" % sp_c + "%12.2fx" % sp_r
        print(row)
    print("-" * 84)
    print("各规模最小值（5 次独立运行 x 10 轮共 50 个样本中的最小）：")
    for n in sizes:
        print("%-9d" % n + "".join("%-*s" % (w, fmt_time(result[n][name]["min"]))
                                   for name in langs))
    print("=" * 84)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(str(s) for s in SIZES))
    ap.add_argument("--runs", type=int, default=5, help="每种语言每个规模的独立运行次数")
    ap.add_argument("--rounds", type=int, default=10, help="每次运行内正式计时的轮数")
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--target", type=float, default=TARGET_SEC)
    ap.add_argument("--naive-demo", action="store_true",
                    help="反例：把进程启动与文件读取一并计入计时")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    os.makedirs(LOGS, exist_ok=True)
    sizes = [int(x) for x in args.sizes.split(",")]
    langs = build_languages()
    print("languages = %s" % list(langs))
    print("python    = %s" % PY_EXE)

    if args.naive_demo:
        return naive_demo(sizes, langs)

    result = {}
    checks = {}
    print("\n[1/2] 正确性核对（one-shot，三语言读同一份 bin 文件）")
    print("%-9s %-24s %-24s %-12s %-12s" % ("N", "Python SUM", "C SUM", "C rel.err", "Rust rel.err"))
    for n in sizes:
        py_val, fsum_val = python_reference(n)
        _, py_once, py_line = run_once(langs["Python"], n)
        # one-shot 与进程内参考必须一致（除非官方基准本身就是错的）
        assert abs(py_once - py_val) <= 1e-9 * max(abs(py_val), 1e-300) + 1e-12, \
            "Python one-shot mismatch %r vs %r" % (py_once, py_val)
        rec = {"python": py_val, "fsum": fsum_val, "python_rel_vs_fsum":
               abs(py_val - fsum_val) / abs(fsum_val) if fsum_val else 0.0}
        errs = []
        for name in ("C", "Rust"):
            if name not in langs:
                continue
            _, val, line = run_once(langs[name], n)
            err = abs(val - py_val) / abs(py_val) if py_val else abs(val - py_val)
            rec[name] = val
            rec[name + "_rel_err"] = err
            errs.append("%-12.3e" % err)
        checks[n] = rec
        print("%-9d %-24.17g %-24s %-12s %-12s" % (
            n, py_val,
            ("%.17g" % rec["C"]) if "C" in rec else "N/A",
            errs[0] if len(errs) > 0 else "N/A",
            errs[1] if len(errs) > 1 else "N/A"))
    print("所有相对误差 <= 1e-9：%s\n" % ("PASS" if all(
        v.get("C_rel_err", 0.0) <= 1e-9 and v.get("Rust_rel_err", 0.0) <= 1e-9
        for v in checks.values()) else "FAIL"))

    print("[2/2] 计时（每种语言 x 每个规模独立运行 %d 次，每次预热 %d 轮 + 正式 %d 轮）"
          % (args.runs, args.warmup, args.rounds))
    for n in sizes:
        result[n] = {}
        for name, cmd in langs.items():
            runs = []
            for r in range(args.runs):
                m = measure_worker(cmd, n, args.warmup, args.rounds, args.target)
                runs.append(m)
                print("  N=%-8d %-7s run %d/%d: median=%-12s min=%-12s k=%-7d rtt=%.1fus"
                      % (n, name, r + 1, args.runs, fmt_time(m["median"]),
                         fmt_time(m["min"]), m["k"], m["rtt_us"]))
            med_of_med = median([m["median"] for m in runs])
            result[n][name] = {
                "median": med_of_med,
                "min": min(m["min"] for m in runs),
                "max": max(m["max"] for m in runs),
                "run_medians": [m["median"] for m in runs],
                "k": runs[0]["k"],
                "rtt_us": median([m["rtt_us"] for m in runs]),
            }

    print_table(sizes, list(langs), result)

    out = {
        "sizes": sizes, "languages": list(langs),
        "runs": args.runs, "rounds": args.rounds, "warmup": args.warmup,
        "target_sec": args.target,
        "times": result, "checks": checks,
        "python_version": sys.version.split()[0],
        "host": os.environ.get("COMPUTERNAME", ""),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    tag = ("_" + args.tag) if args.tag else ""
    with open(os.path.join(LOGS, "benchmark_raw%s.json" % tag), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n原始数据已写入 logs/benchmark_raw%s.json" % tag)
    return 0


def naive_demo(sizes, langs):
    """反例：整进程计时（含进程启动 + 8MB 文件读取），用于说明计时口径的重要性。"""
    print("\n=== 反例：把进程启动与文件读取算进计时（每规模 5 次，取中位数）===")
    print("%-9s %-12s %-12s %-12s" % ("N", "Python", "C", "Rust"))
    rows = {}
    for n in sizes:
        line = "%-9d" % n
        rows[n] = {}
        for name, cmd in langs.items():
            pa = os.path.join(DATA, "a_%d_f64.bin" % n)
            pb = os.path.join(DATA, "b_%d_f64.bin" % n)
            vals = []
            for _ in range(5):
                t0 = time.perf_counter()
                cp = subprocess.run(cmd + [pa, pb], capture_output=True, text=True)
                t1 = time.perf_counter()
                if cp.returncode != 0:
                    raise RuntimeError(cp.stderr)
                vals.append(t1 - t0)
            rows[n][name] = median(vals)
        for name in langs:
            line += "%-12s" % fmt_time(rows[n][name])
        print(line)
    print("说明：N=10^4 时 C 的真实点积只有几微秒，整进程计时把它埋进启动开销里，")
    print("      会得出「C 与 Python 差不多」的错误结论 —— 这正是必须做应答式协议的原因。")
    out = {"naive_whole_process": rows, "sizes": sizes, "languages": list(langs)}
    with open(os.path.join(LOGS, "naive_whole_process.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
