#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_runs.py —— 合并多次完整基准的结果，得到稳健的官方数据。

背景：本机是共享环境（实验期间同时有工具链安装、其它实验在跑），单次完整基准的
中位耗时在不同时刻会有 10%~40% 的波动（CPU 频率/温度/后台负载）。因此把
logs/benchmark_raw_run{1,2,3}.json 三次完整基准合并：

    每个「规模 × 语言」最终耗时 = 全部「运行中位数」的中位数（3 次基准 × 每次 5 次独立运行 = 15 个中位数）

并记录三次基准各自的数值与相互偏差，供报告如实说明（不隐藏波动）。
输出 logs/benchmark_raw.json（官方数据）+ logs/stability.json（稳定性统计）。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")


def median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 == 1 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def main():
    paths = [os.path.join(LOGS, "benchmark_raw_run%d.json" % i) for i in (1, 2, 3)]
    runs = [json.load(open(p, encoding="utf-8")) for p in paths if os.path.exists(p)]
    if not runs:
        print("没有 benchmark_raw_run*.json")
        return 1
    base = runs[0]
    sizes = [int(x) for x in base["sizes"]]
    langs = base["languages"]
    per_session = base["runs"]

    times, stability = {}, {}
    for n in sizes:
        times[str(n)] = {}
        stability[str(n)] = {}
        for name in langs:
            meds = [r["times"][str(n)][name]["median"] for r in runs]
            all_run_meds = []
            for r in runs:
                all_run_meds += r["times"][str(n)][name]["run_medians"]
            official = median(all_run_meds)
            times[str(n)][name] = {
                "median": official,
                "min": min(r["times"][str(n)][name]["min"] for r in runs),
                "max": max(r["times"][str(n)][name]["max"] for r in runs),
                "per_session_medians": meds,
                "num_run_medians": len(all_run_meds),
                "k": base["times"][str(n)][name]["k"],
                "rtt_us": median([r["times"][str(n)][name]["rtt_us"] for r in runs]),
            }
            spread = (max(meds) - min(meds)) / min(meds) * 100.0
            stability[str(n)][name] = {
                "session_medians": meds,
                "spread_pct": spread,
            }

    out = {
        "sizes": sizes,
        "languages": langs,
        "runs": per_session,
        "sessions": len(runs),
        "total_runs": per_session * len(runs),
        "rounds": base["rounds"],
        "warmup": base["warmup"],
        "target_sec": base["target_sec"],
        "times": times,
        "checks": base["checks"],
        "python_version": base["python_version"],
        "timestamp": base["timestamp"],
        "merge": "median of all run-medians across %d benchmark sessions" % len(runs),
    }
    with open(os.path.join(LOGS, "benchmark_raw.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(LOGS, "stability.json"), "w", encoding="utf-8") as f:
        json.dump(stability, f, ensure_ascii=False, indent=1)

    print("%-9s %-7s %12s %12s %12s %10s" % ("N", "lang", "s1", "s2", "s3", "spread%"))
    for n in sizes:
        for name in langs:
            st = stability[str(n)][name]
            m = st["session_medians"]
            print("%-9d %-7s %12s %12s %12s %9.1f%%" % (
                n, name,
                *["%.6g" % x for x in m], st["spread_pct"]))
    print("\n官方数据（跨 %d 次基准的 15 个运行中位数的中位数）已写入 logs/benchmark_raw.json" % len(runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
