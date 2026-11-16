# 邹玥（学号 2025311160，数字媒体艺术2班） · 第03/04讲 实验代码

2026 秋《数字媒体程序设计》· 第2章 编程语言概论
在线地址：https://github.com/ShiZiyukuo/dsp-2026-lab03-04
同步时间：2026-11-17 02:26

配套实验报告（两讲各 6 页，日期均为 2026-11-16）：
- 第03讲：矩阵乘法四层实现—从 Verilog 到 CUDA
- 第04讲：Scaled Dot-Product 计算与 Python、C、Rust 效率对比

---

## 第03讲 矩阵乘法四层实现—从 Verilog 到 CUDA（`第03讲-矩阵乘法四层实现/`）

| 文件 | 说明 |
|---|---|
| `matmul.c` | C 版 3×3 矩阵乘法，三重循环 + 逐项 PASS/FAIL 比对 + 校验和 |
| `matmul_O0.s` / `matmul_O2.s` | 真实 **gcc 16.2.0 `-S`** 输出（AT&T 语法），460 行 / 285 行 |
| `matmul.v` / `tb_matmul.v` | Verilog RTL：generate+genvar 例化 27 个 mul8s + testbench |
| `matmul.cu` / `matmul_musa.cu` / `musa_diff.txt` | CUDA 核函数、MUSA 前缀改写版、两者 unified diff |
| `matmul_cu_ref.c` | 把 CUDA 核函数累加循环搬到 CPU 的等价实现（本机无 nvcc 时的语义验证） |
| `bench_matmul.c` | `-O0` vs `-O2` 耗时基准（2000 万轮 × 3 次取中位数） |
| `appendix_msvc_cl/` | 附录：MSVC `cl /FA` 的 MASM 汇编（先前环境对照，正文数字不用它） |
| `README.md` | 五维度对照表（并行粒度 / 数据落点 / 调度归属 / 代码行数 / 出错方式）+ 复现命令 |
| `_运行日志/` | 全部真实终端输出（run_gcc_O0.txt、run_gcc_O2.txt、bench_gcc.txt、sim.txt…） |

关键真实结果：`C = [30,24,18; 84,69,54; 138,114,90]`，`CHECKSUM = 621`；
C(-O0) / C(-O2) / Verilog 仿真（Icarus Verilog 12.0）/ CUDA-CPU 等价实现四路均 **9/9 PASS**；
`-O0` 2.8780 s → `-O2` 0.3370 s（**8.54×**），汇编 **460 → 285 行**；
`-O0` 内层 `c[i][j]+=a[i][k]*b[k][j]` 对应 `imull` + `leal`（第 138、139 行），`-O2` 把 k 循环展开成 3 `imull` + 2 `addl`；
向量化只出现在校验和规约（3 条 `paddd`），矩阵乘法本身未向量化。

## 第04讲 Scaled Dot-Product 效率对比（`第04讲-ScaledDotProduct/`）

| N | Python | C (gcc -O2) | Rust (opt-level=3) | C/Python | Rust/Python |
|---|---|---|---|---|---|
| 1e4 | 983.08 µs | 9.94 µs | 9.50 µs | 98.9× | 103.5× |
| 1e5 | 9.409 ms | 97.61 µs | 102.76 µs | 96.4× | 91.6× |
| 1e6 | 97.725 ms | 1.162 ms | 1.170 ms | 84.1× | 83.5× |

（3 次完整基准 × 每次 5 次独立运行 × 10 轮计时 = 15 次运行 / 150 样本取中位数；消融：`-O0 vs -O2 = 3.43×`、`rustc opt-level 0 vs 3 = 5.38×`）

| 文件 | 说明 |
|---|---|
| `gen_data.py` | 生成 N=10⁴/10⁵/10⁶ 的 `a_*_f64.bin`、`b_*_f64.bin`（seed=20261117，三语言读同一份数据） |
| `dot.py` / `dot.c` / `dot.rs` | 三语言统一接口 `dot(a,b) -> f64`，仅用标准库，循环内消费结果 |
| `benchmark.py` | 统一计时协议：预热 3 轮 + 正式 10 轮取中位数，3 次完整基准 × 每种语言 5 次独立运行 |
| `test_dot.py` | 5 个边界用例（n=0 / n=1 / 整数精确 / 全零 / 极大极小混合）+ 长度不匹配异常断言 |
| `prompt_v1.md` / `prompt_v2.md` | 按「输入/输出/约束/示例」四要素写的提示词全文，v2 只改「计时口径」一个变量 |
| `ablation.py` | 消融对照：`-O0` vs `-O2`、Rust opt-level=0 vs 3、整进程计时 vs 应答式计时 |
| `merge_runs.py` / `make_figs.py` / `build_all.bat` | 3 次基准合并、图表生成、一键构建脚本 |
| `README.md` | 跑法、文件说明、3×3 耗时对比表 |
| `_运行日志/` | 三语言原始计时输出、校验和、编译日志、消融实验日志 |

三语言读同一份 bin：三个规模校验和逐位相同（相对误差 0），5 个边界用例 5 PASS。

---

## 环境说明（如实记录）

- 本机原本没有 gcc / rustc / iverilog / CUDA Toolkit，实验中现场安装：
  - **gcc 16.2.0**（MSYS2 mingw-w64，`-O2`；`-S` 输出 AT&T 汇编）
  - Rust：rustup + rustc **1.100.0**（`x86_64-pc-windows-msvc`，`-C opt-level=3`≈`--release`）
  - Verilog：**Icarus Verilog 12.0**（本地安装，`-g2012` 仿真）
  - CUDA：**无 nvcc**，`matmul.cu` 未编译；用 CPU 等价实现验证算法语义，未编造 GPU 耗时
- 运行环境：Windows 11 x64 + Visual Studio 2022 Community，Python 3.12.14。
