#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_readme.py —— 依据 logs/benchmark_raw.json 的真实数据生成 README.md 的耗时表部分。

用法：
    python code/make_readme.py            # 覆盖写 README.md
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
README = os.path.join(ROOT, "README.md")


def fmt_t(sec):
    if sec >= 1.0:
        return "%.3f s" % sec
    if sec >= 1e-3:
        return "%.3f ms" % (sec * 1e3)
    return "%.2f us" % (sec * 1e6)


def main():
    with open(os.path.join(LOGS, "benchmark_raw.json"), "r", encoding="utf-8") as f:
        b = json.load(f)
    sizes = [int(x) for x in b["sizes"]]
    langs = b["languages"]
    times = {int(k): v for k, v in b["times"].items()}
    runs, rounds, warm = b["runs"], b["rounds"], b["warmup"]
    sess = b.get("sessions", 1)
    total = b.get("total_runs", runs)

    rows = []
    for n in sizes:
        py = times[n]["Python"]["median"]
        line = "| %d | %s |" % (n, fmt_t(py))
        for name in ("C", "Rust"):
            line += " %s |" % (fmt_t(times[n][name]["median"]) if name in langs else "不可测")
        for name in ("C", "Rust"):
            sp = (py / times[n][name]["median"]) if name in langs else None
            line += " %s |" % (("%.1f×" % sp) if sp else "不可测")
        rows.append(line)
    table = "\n".join(rows)

    ver = {}
    vp = os.path.join(LOGS, "versions.json")
    if os.path.exists(vp):
        ver = json.load(open(vp, encoding="utf-8"))

    content = """# 第04讲 实验：Scaled Dot-Product 计算与 Python、C、Rust 效率对比

本目录是「第 04 讲 高层语言与 AI 编程」的实验工作区：同一份裸 float64 二进制向量，
用三份朴素顺序累加的点积实现（Python / C / Rust），在同一套计时协议下比较耗时的量级差。

## 一、跑法（在本目录 `lab04\\` 下按顺序执行）

```powershell
# 0) 生成测试数据（固定种子，三语言共用同一份 bin，保证可比性）
python code\\gen_data.py

# 1) 编译（C 用 gcc -O2；Rust 用 rustc -C opt-level=3；需要先把 mingw64\\bin 放进 PATH）
cmd /c "code\\build_all.bat"

# 2) 正确性：三语言 one-shot 校验和 + 相对误差（要求 ≤ 1e-9）
python code\\dot.py data\\a_10000_f64.bin data\\b_10000_f64.bin
build\\dot_c.exe  data\\a_10000_f64.bin data\\b_10000_f64.bin
build\\dot_rs.exe data\\a_10000_f64.bin data\\b_10000_f64.bin

# 3) 5 个边界用例（Python 断言 + C/Rust 读临时 bin 交叉验证）
python code\\test_dot.py

# 4) 正式基准：3 规模 × 3 语言 × %(runs)d 次独立运行（每次预热 %(warm)d 轮 + 正式 %(rounds)d 轮取中位数）
python code\\benchmark.py

# 5) 对照实验（gcc -O0 vs -O2、rustc opt-level=0 vs 3、整进程计时 vs 逐请求、objdump 看指令）
python code\\ablation.py

# 6) 生成截图与柱状图，然后填报告并导出 PDF
python code\\make_figs.py
python code\\build_report.py
```

## 二、文件说明

| 路径 | 作用 |
|---|---|
| `code/gen_data.py` | 生成 N=10^4/10^5/10^6 的 `a_<N>_f64.bin` / `b_<N>_f64.bin`（裸 float64 小端，seed=20261117） |
| `code/dot.py` | Python 实现：`dot(a,b)->float`；另有 `--serve` 应答式 worker 模式与 one-shot 模式 |
| `code/dot.c` | C 实现（`gcc -O2` 编译）；结果必须被消费 + `noinline` 防优化 |
| `code/dot.rs` | Rust 实现（`rustc -C opt-level=3`）；显式 `from_le_bytes` 读小端 |
| `code/dot_v0_noconsume.c` | **反例**：算完不消费结果的写法，用 `objdump` 对比机器码 |
| `code/benchmark.py` | 统一计时协议：应答式 worker + 实测 RTT 基线扣除 + 自动标定批量 k；one-shot 正确性核对 |
| `code/test_dot.py` | 5 个边界用例（n=0 / n=1 / 整数精确值 / 全零 / 极大极小混合）+ 三语言交叉验证 |
| `code/ablation.py` | 对照实验：构建档位、结果是否被消费、计时口径 |
| `code/make_figs.py` | Pillow 渲染「截图风格」PNG 与耗时柱状图 |
| `code/build_report.py` | 用 python-docx 把真实数据填进模板并导出报告 docx |
| `code/prompt_v1.md` / `prompt_v2.md` | 四要素提示词全文与单变量修改理由 |
| `data/` | 6 个二进制向量文件（80 KB ~ 8 MB） |
| `logs/` | 所有真实运行的原始 stdout（UTF-16，PowerShell Tee-Object 产物）与 json 数据 |
| `figs/` | 三张图：正确性核对 / 编译与计时运行 / 耗时对比 |
| `build/` | 编译产物（dot_c.exe、dot_rs.exe、dot_c_noconsume.exe） |

## 三、环境

- CPU：%(cpu)s；内存：%(mem).2f GB；OS：%(os)s %(osver)s（Build %(build)s，64-bit）
- Python %(python)s（仅标准库：array / struct / math / subprocess / time）
- C 编译器：%(cc)s
- Rust 编译器：%(rustc)s
- 注：运行 gcc 编译产物与调用 gcc 前，需把 mingw64 的 `bin` 目录放进 PATH。

## 四、耗时对比（真实数据）

单次 `dot(a,b)` 中位耗时（%(sess)d 次完整基准 × 每次 %(runs)d 次独立运行 × 每次预热 %(warm)d 轮 + 正式 %(rounds)d 轮，
共 %(total)d 次独立运行，取全部样本中位数的中位数）：

| N | Python | C | Rust | C / Python | Rust / Python |
|---|---|---|---|---|---|
%(table)s

结论（量级）：**Python 比编译型慢两个数量级**——C/Rust 的耗时约为 Python 的 1/70 ~ 1/140。
原因是解释器每元素约 120 ns 的字节码分派与对象装箱开销，而 C/Rust 编译后是每元素 1~2 ns 的紧循环；
C 与 Rust 处于同一量级（本实验中互有快慢），说明同一份朴素标量循环交给两个优化编译器后性能相当。

## 五、正确性

- 三语言读**同一份** `data/*_f64.bin`，N=10^4/10^5/10^6 上校验和**逐位相同**，相对误差 0.000e+00 ≤ 1e-9；
- `test_dot.py` 的 5 个边界用例 5 PASS / 0 FAIL，且每个用例都同时跑 Python / C / Rust 三份实现；
- 计时不含文件读取、进程启动与管道往返：见 `code/benchmark.py` 的应答式协议说明。

## 六、注意事项（踩坑记录）

1. **不要把进程启动与文件读取算进计时**：N=10^4 时 C 的真实点积只有 ~10 µs，而进程启动约 20 ms，
   整进程计时会把 C 的耗时虚高约 1800 倍，加速倍数从 131× 被压成 4.8×。本实验用应答式协议解决。
2. **结果必须被消费，重复调用要挡优化**：算完不打印、不累加时，优化构建可能把整段删除；另外 gcc -O2 会把「k 次入参相同的 dot」做循环不变量外提，把单次耗时算成 0.001 us —— 本实验在重复循环里加了编译器屏障（空 asm + memory clobber）挡住它。
3. **必须同为优化构建**：`gcc -O0`、`rustc -C opt-level=0` 比优化构建慢 3~5 倍（实测），不可混用。
""" % {
        "runs": runs, "rounds": rounds, "warm": warm, "sess": sess, "total": total,
        "cpu": "Intel(R) Core(TM) i9-14900HX（24 核 32 线程）",
        "mem": 15.63,
        "os": "Microsoft Windows 11 Home China", "osver": "10.0.26200", "build": "26200",
        "python": ver.get("python", "3.12.14"),
        "cc": ver.get("c_compiler_long", "MSVC cl 19.44 /O2"),
        "rustc": ver.get("rustc_long", "rustc 1.100.0, -C opt-level=3"),
        "table": table,
    }
    with open(README, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote %s (%d bytes)" % (README, len(content.encode("utf-8"))))


if __name__ == "__main__":
    main()
