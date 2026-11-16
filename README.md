# 作业代码附件（第03讲 + 第04讲）

2026 秋《数字媒体程序设计》· 第2章 编程语言概论
导出时间：2026-11-17 01:42

配套实验报告：
- `../output/第03讲-矩阵乘法四层实现—从 Verilog 到 CUDA-实验报告.pdf`
- `../output/第04讲-Scaled Dot-Product 计算与 Python、C、Rust 效率对比-实验报告.pdf`

---

## 第03讲 矩阵乘法四层实现—从 Verilog 到 CUDA（`第03讲-矩阵乘法四层实现/`）

| 文件 | 说明 |
|---|---|
| `matmul.c` | C 版 3×3 矩阵乘法，三重循环 + 逐项 PASS/FAIL 比对 + 校验和 |
| `matmul_O0.asm` / `matmul_O2.asm` | 真实 `cl /FA` 汇编输出（MASM 语法），-Od 658 行 / -O2 517 行 |
| `matmul_O0_src.asm` / `matmul_O2_src.asm` | `cl /FAs` 带源码行注释版（814 / 654 行） |
| `matmul_asm_annotated.txt` | 内层 `imul`+`add` 与 `c[i][j]+=a[i][k]*b[k][j]` 的逐行对照（含行号） |
| `matmul.v` / `tb_matmul.v` | Verilog RTL：generate+genvar 例化 27 个 mul8s + testbench |
| `matmul.cu` / `matmul_musa.cu` / `musa_diff.txt` | CUDA 核函数、MUSA 前缀改写版、两者 unified diff |
| `matmul_cu_ref.c` | 把 CUDA 核函数累加循环搬到 CPU 的等价实现（本机无 nvcc 时的语义验证） |
| `bench_matmul.c` | -Od vs /O2 耗时基准（2000 万轮） |
| `README.md` | 一页对照表（并行粒度 / 数据在哪 / 谁调度 / 代码行数 / 出错方式）+ 复现命令 |
| `_运行日志/` | 全部真实终端输出（run_cl_Od.txt、run_cl_O2.txt、bench_O0_O2.txt、sim.txt…） |

关键真实结果：`C = [30,24,18; 84,69,54; 138,114,90]`，`CHECKSUM = 621`，
C / C-O2 / Verilog 仿真（Icarus Verilog 12.0）/ CUDA-CPU 等价实现四路均为 **9/9 PASS**；
`-Od` 2.881 s → `/O2` 0.347 s（**8.30×**），汇编 658 → 517 行，-O2 未向量化（无 SIMD 指令）。

## 第04讲 Scaled Dot-Product 效率对比（`第04讲-ScaledDotProduct/`）

| 文件 | 说明 |
|---|---|
| `gen_data.py` | 生成 N=10⁴/10⁵/10⁶ 的 `a_*_f64.bin`、`b_*_f64.bin`（seed=20261117，三语言读同一份数据） |
| `dot.py` / `dot.c` / `dot.rs` | 三语言统一接口 `dot(a,b) -> f64`，仅用标准库，循环内消费结果 |
| `benchmark.py` | 统一计时协议：预热 3 轮 + 正式 10 轮取中位数，3 次完整基准 × 每种语言 5 次独立运行 |
| `test_dot.py` | 5 个边界用例（n=0 / n=1 / 整数精确 / 全零 / 极大极小混合）+ 长度不匹配异常断言 |
| `prompt_v1.md` / `prompt_v2.md` | 按「输入/输出/约束/示例」四要素写的提示词全文，v2 只改「计时口径」一个变量 |
| `ablation.py` | 消融对照：-Od vs /O2、Rust opt-level=0 vs 3、整进程计时 vs 应答式计时 |
| `merge_runs.py` / `make_figs.py` / `build_all.bat` | 3 次基准合并、图表生成、一键构建脚本 |
| `README.md` | 跑法、文件说明、3×3 耗时对比表 |
| `_运行日志/` | 三语言原始计时输出、校验和、编译日志、消融实验日志 |

关键真实结果（中位数，3 次完整基准 × 15 次独立运行合并）：C 相对 Python 约 **110×~112×**，
Rust 与 C 同量级（约 100×~110×），三语言结果相对误差 **0**（逐位一致），5 个边界用例 **5 PASS**。

---

## 环境说明（如实记录）

- 本机原本没有 gcc / rustc / iverilog / CUDA Toolkit，实验中现场安装/替代：
  - C 编译：**MSVC cl.exe 19.44**（`/Od`≈`-O0`、`/O2`；`/FA` 汇编为 MASM 语法，非 gcc `-S` 的 AT&T）
  - Rust：rustup + rustc **1.100.0**（`x86_64-pc-windows-msvc`，`-C opt-level=3`≈`--release`）
  - Verilog：**Icarus Verilog 12.0**（本地安装，`-g2012` 仿真）
  - CUDA：**无 nvcc**，`matmul.cu` 未编译；用 CPU 等价实现验证算法语义，未编造 GPU 耗时
- 运行环境：Windows x64 + Visual Studio 2022 Community，Python 3.12.14。
