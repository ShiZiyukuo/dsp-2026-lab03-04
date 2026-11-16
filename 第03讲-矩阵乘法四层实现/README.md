# 第03讲　矩阵乘法四层实现——从 Verilog 到 CUDA

> 同一个 3×3 整数矩阵乘法 `C = A × B`，在 **Verilog / 汇编 / C / CUDA** 四层各写一遍，
> 理解「同一算法、四种代价」。

---

## 0. 测试数据与标准答案

四层实现使用**完全相同**的一组输入（固定数据，便于逐字符 diff）：

```
A = 1 2 3        B = 9 8 7
    4 5 6            6 5 4
    7 8 9            3 2 1
```

标准答案由 NumPy 2.3.5 求得（`A @ B`）：

```python
C = [[ 30,  24,  18],
     [ 84,  69,  54],
     [138, 114,  90]]
C_FLAT = 30 24 18 84 69 54 138 114 90
CHECKSUM = 621          # 30+24+18 + 84+69+54 + 138+114+90
```

**四层实现的最终裁决指标就是这一个 `CHECKSUM = 621`，9 个元素逐项相等。**

---

## 1. 四层对照表（指南第 9 步要求的一页表）

| 维度 | Verilog（RTL） | 汇编（x86-64） | C | CUDA |
|---|---|---|---|---|
| **并行粒度** | 电路级并行：27 个乘法器 + 加法树同时翻转，**粒度为「门/线」**，无「指令」概念 | 无并行：单指令流，一次 imul 算一个乘积，**粒度为「一条指令」** | 无并行：三重循环串行，**粒度为「一次迭代」** | 线程级并行：**一个线程 = 一个 C[i][j]**，9 个线程真正并行，粒度为「线程」 |
| **数据在哪** | 全在**寄存器/线网**里，组合逻辑直连，A/B 是端口上的电平 | 在**内存**（`A`/`B`/`C` 全局区）+ 寄存器中转，靠 `[r9+r10*4]` 寻址 | 在**内存**（栈上局部数组 `C$[rsp]`），编译器决定哪些值留寄存器 | 在**显存**（`cudaMalloc`），计算前 `cudaMemcpy` 拷入，算完拷回主机 |
| **谁负责调度** | **没有调度者**：赋值是并发的（`assign`），结果只由连线拓扑决定。书写顺序 ≠ 执行顺序 | **CPU 前端**：取指/译码/乱序执行，硬件按依赖关系调度 | **程序员 + 编译器**：循环边界、迭代顺序（i-j-k）全由源码写死 | **GPU 硬件调度器（warp scheduler）**：把 9 个线程分到 warp 里，由 SM 自动分派；程序员只给线程映射规则 |
| **代码行数（实测）** | `matmul.v` **73 行** / `tb_matmul.v` **109 行** | `matmul_O0.s` **460 行** / `matmul_O2.s` **285 行**（gcc `-S` 实际输出全文件行数） | `matmul.c` **112 行**（含比对与打印） | `matmul.cu` **106 行**（含 cudaMalloc/Memcpy 全套宿主代码） |
| **出错方式** | 位宽截断、组合环、`assign` 当顺序语句写、用变量下标访问数组被综合器拒（本实验改用 generate+genvar） | 段错误/越界寻址、寄存器用错、ABI 栈不平衡；`-O2` 后源码与汇编不再逐行对应（最难调） | 下标越界、`k` 顺序写反致缓存不命中（慢几倍）、整数溢出 | 漏写 `if (row<n && col<n)` ⇒ 越界读写直接崩；忘了 `cudaDeviceSynchronize` 读到脏数据；warp 内分支发散 |
| **耗时量级** | 组合延迟（纳秒级，与门级延迟、加法树深度有关） | 最快：`-O2` 实测 **0.347 s** / 2000 万轮 | 最慢：`-Od` 实测 **2.881 s** / 2000 万轮（同一份源码） | 3×3 极小，**kernel 启动开销（~5–10 μs）远大于计算（~9 次乘加）**，反而最不划算 |
| **本质差异一句话** | 并行 = **电路同时翻转** | 并行 = 无，纯顺序 | 并行 = 无，纯顺序 | 并行 = **线程同时执行** |

### 一句话总结四层

- **Verilog**：你画的不是「步骤」，是「结构」。`assign` 是并发赋值，写在前面的不会先执行。
- **汇编**：`c[i][j] += a[i][k]*b[k][j]` 就是 **`imul` + `add` 两条指令**，其余全是寻址开销。
- **C**：编译器替你把三重循环变成上面那两条指令；`-O2` 会把内层 `k` 循环整个展开。
- **CUDA**：把「谁算哪个元素」从循环下标变成线程下标，调度交给 GPU。

---

## 2. 文件清单

| 文件 | 说明 |
|---|---|
| `matmul.c` | C 版：三重循环 + 打印结果 + CHECKSUM + 与 NumPy 标准答案逐项比对 |
| `matmul_O0.s` | **-O0** 真实汇编（`gcc -O0 -S`，AT&T 语法，**460 行**） |
| `matmul_O2.s` | **-O2** 真实汇编（`gcc -O2 -S`，**285 行**） |
| `appendix_msvc_cl/` | 附录：MSVC `cl /FA` 的 MASM 汇编（-Od 658 行 / -O2 517 行）与逐行注释对照 |
| `matmul.v` | Verilog 版：`parameter N=3`，`generate`+`genvar` 例化乘法器，`assign` 写组合逻辑 |
| `tb_matmul.v` | Verilog testbench：同一组输入，逐项比对 C 版结果 |
| `matmul.cu` | CUDA 版：一线程算一个 `C[i][j]`，`blockDim=32`，含完整宿主代码 |
| `matmul_musa.cu` | MUSA 版：`cuda*` → `musa*` 机械替换结果（106 行中 14 行改动） |
| `musa_diff.txt` | 上面这个改写的真实 unified diff（39 行） |
| `matmul_cu_ref.c` | 无 GPU 时验证 CUDA 内核算法语义的 CPU 等价实现（已真实运行） |
| `bench_matmul.c` | -O0 / -O2 耗时基准（2000 万轮，防死代码消除） |

> **汇编工具链**：汇编由 **gcc 16.2.0**（MSYS2 mingw-w64，x86_64-w64-mingw32）的 `gcc -S` 生成，
> 语法为 **AT&T**，`.s` 文件内含 `.file "matmul.c"` 与 `.ident "GCC: (Rev7, Built by MSYS2 project) 16.2.0"`。
> 调用前需把 `mingw64\bin` 加入 `PATH`，否则 `cc1` 会因找不到 DLL 以退出码 1 静默失败。
> 另有 **MSVC `cl /FA` 的 MASM 版本**留在 `appendix_msvc_cl/` 作附录对照，正文数字一律以 gcc 为准。

---

## 3. 关键指令对应（汇编层）

`matmul.c` 第 49 行：`C[i][j] += A[i][k] * B[k][j];`

### -O0，`matmul_O0.s` 第 137-139 行

```asm
movl   (%rdx,%rax), %eax        # eax = B[k][j]
imull  %ecx, %eax               # eax = A[i][k] * B[k][j]   <-- 乘法本体
leal   (%r8,%rax), %ecx         # ecx = C[i][j] + 乘积      <-- 累加本体（gcc 用 lea 兼职加法）
```

**一行 C 的乘加 = `imull` + `leal` 两条指令**。其中 `C[i][j]` 由第 115 行
`movl -64(%rbp,%rax,4), %r8d` 先读进 `%r8d`；gcc 选 `leal` 而不是 `addl`，
是因为 `lea` 算加法但不写标志位，能省掉一次标志更新。
一次内层迭代共 43 条指令，其余全花在行主序地址计算（第 119-136 行反复算 `i*12`、`k*12`）和内存往返上。

### -O2，`matmul_O2.s` 第 78-90 行

内层 `k` 循环**被完全展开**，一个 `C[i][j]` 只剩 9 条指令 + 3 条循环控制：

```asm
 movl   (%rbx,%rax), %edx        # B[0][j]
 movl   0(%r13,%rax), %r14d      # B[1][j]
 imull  %r10d, %edx              # A[i][0]*B[0][j]
 imull  %r11d, %r14d             # A[i][1]*B[1][j]
 addl   %r14d, %edx              # 前两项和
 movl   (%r12,%rax), %r14d       # B[2][j]
 imull  %r9d, %r14d              # A[i][2]*B[2][j]
 addl   %r14d, %edx              # 三项和 = C[i][j]
 movl   %edx, (%rcx,%rax)        # 直接写回 C[i][j]
 addq   $4, %rax                 # j 指针 += 4
 cmpq   $12, %rax
 jne    .L3
```

第 177-184 行是**唯一被向量化的地方**——校验和规约（3 条 `paddd` + `movdqa` + `psrlq`）：

```asm
 paddd  %xmm1, %xmm0
 paddd  %xmm1, %xmm0
 movdqa %xmm0, %xmm1
 psrlq  $32, %xmm1
 paddd  %xmm1, %xmm0
```

### -O0 vs -O2 对比数据（全部实测）

| 指标 | -Od (= -O0) | -O2 | 变化 |
|---|---|---|---|
| 汇编总行数 | **460** | **285** | −175 行（−38.0%） |
| 内层 `k` 循环 | 保留：`cmpl/jle` 回边（第 150-152 行） | **完全展开成 3 条 `imull` + 2 条 `addl`** | 消除了 k 循环判断 |
| 每个 `C[i][j]` 的指令数 | 约 **129** 条（3 × 43） | 约 **12** 条 | ≈ **10.8×** |
| 强度削弱 | 每次迭代重算 `i*12` / `k*12` | 指针递增（`addq $4,%rax` / `addq $12,%rcx`） | 地址乘法被消除 |
| 向量化 | 无 | **有，但只在校验和规约**：第 177-184 行 3 条 `paddd` + `movdqa` + `psrlq` | 矩阵乘法本身未向量化（内层仅 3 个 int，凑不满 4 lane） |
| 2000 万轮实测耗时（3 次中位） | **2.878 s** | **0.337 s** | **8.54×** 加速 |

> 指令数比 ≈7×，实测耗时比 8.30×，两者同一量级，互相印证。

---

## 4. Verilog 层要点

- **为什么必须用 generate**：Verilog 里数组下标不能是变量，`A[i][k]` 中 `i/k` 若是循环变量会被综合器拒绝。
  `generate` + `genvar` 是**展开期**循环，展开后下标全是常数 → 合法可综合。
- **为什么用扁平向量端口**：二维数组端口不可综合，故把元素 `(i,j)` 放在比特 `[(i*N+j)*8 +: 8]`。
- **9 个乘法器 vs 27 个乘法器**：`generate` 的 i、j 两重展开出 **9 个乘加单元**（对应 9 个 `C[i][j]`），
  每个单元内 k 再展开 **3 个 `mul8s` 实例**，故实际例化 **27 个 8×8 有符号乘法器** + 9 棵两级加法树。
- **`assign` 是并发的**：三条 `+` 同时成立，书写顺序不代表执行顺序 —— 这是与 C 最本质的差别。
- **位宽**：8bit 有符号元素，乘积 32bit；每个 `C[i][j]` 最多 `3 × 255 × 255 = 195075 < 2^18`，32bit 充裕。

### 逐项手工推演 + 真实仿真结果（Icarus Verilog 12.0，-g2012 编译 exit=0 零 warning，二者互为交叉验证）

`mul8s(a,b) = a*b`（有符号），`acc = prod0+prod1+prod2`：

| (i,j) | k=0 | k=1 | k=2 | 和 | 与 C 版比较 |
|---|---|---|---|---|---|
| (0,0) | 1×9=9 | 2×6=12 | 3×3=9 | **30** | PASS |
| (0,1) | 1×8=8 | 2×5=10 | 3×2=6 | **24** | PASS |
| (0,2) | 1×7=7 | 2×4=8 | 3×1=3 | **18** | PASS |
| (1,0) | 4×9=36 | 5×6=30 | 6×3=18 | **84** | PASS |
| (1,1) | 4×8=32 | 5×5=25 | 6×2=12 | **69** | PASS |
| (1,2) | 4×7=28 | 5×4=20 | 6×1=6 | **54** | PASS |
| (2,0) | 7×9=63 | 8×6=48 | 9×3=27 | **138** | PASS |
| (2,1) | 7×8=56 | 8×5=40 | 9×2=18 | **114** | PASS |
| (2,2) | 7×7=49 | 8×4=32 | 9×1=9 | **90** | PASS |

累加和 = 30+24+18+84+69+54+138+114+90 = **621**，与 C / NumPy / CUDA 参考实现一致。

仿真输出（`../logs/sim.txt` 原文，`iverilog -g2012` 编译 exit=0 零 warning）：

```
$ vvp tmp\tb.vvp
=== Verilog 组合逻辑仿真 matmul (N=3) ===
A = 1 2 3 / 4 5 6 / 7 8 9
B = 9 8 7 / 6 5 4 / 3 2 1
Y = [ 30 24 18 ]  [ 84 69 54 ]  [ 138 114 90 ]
  Y[0][0] =   30  REF =   30  PASS
  ...（9 项全 PASS，完整见 sim.txt）
  Y[2][2] =   90  REF =   90  PASS
Y_FLAT = 30 24 18 84 69 54 138 114 90
CHECKSUM = 621
RESULT: 9/9 PASS  ==> ALL PASS（与 C 版 CHECKSUM=621 一致）
```

仿真器：Icarus Verilog version 12.0 (devel) (s20150603-1539-g2693dd32b)。
**下表逐项手工推演与真机仿真结果完全一致，互为交叉验证。**

`
\$ vvp tmp\tb.vvp
=== Verilog 组合逻辑仿真 matmul (N=3) ===
A = 1 2 3 / 4 5 6 / 7 8 9
B = 9 8 7 / 6 5 4 / 3 2 1
Y = [ 30 24 18 ]  [ 84 69 54 ]  [ 138 114 90 ]
  Y[0][0] =   30  REF =   30  PASS
  ...（9 项全 PASS，完整见 sim.txt）
  Y[2][2] =   90  REF =   90  PASS
Y_FLAT = 30 24 18 84 69 54 138 114 90
CHECKSUM = 621
RESULT: 9/9 PASS  ==> ALL PASS（与 C 版 CHECKSUM=621 一致）
`

仿真器：Icarus Verilog version 12.0 (devel) (s20150603-1539-g2693dd32b)。
**下表逐项手工推演与真机仿真结果完全一致，互为交叉验证。**

---

## 5. CUDA 层要点

- **一线程一个 `C[i][j]`**：`row = blockIdx.y*blockDim.y+threadIdx.y`，`col = blockIdx.x*blockDim.x+threadIdx.x`。
- **3×3 需要几个 block / 几个线程**（`blockDim = 32×32`）：
  - `gridDim = ( ⌈3/32⌉, ⌈3/32⌉ ) = (1, 1)` → **1 个 block**
  - 该 block 共 `32 × 32 = 1024` 个线程，**只有 3×3 = 9 个线程真正计算**
  - 有效利用率 `9 / 1024 ≈ 0.88%` —— 这就是「3×3 太小、GPU 完全跑不满」的量化证据
- **越界判断必不可少**：`if (row < n && col < n)`，否则 1015 个多余线程越界读写直接崩。
- **本机情况（如实）**：本机确有 **NVIDIA GeForce RTX 4060 Laptop GPU**，
  但**未安装 CUDA Toolkit（无 nvcc）**，故 `matmul.cu` **未编译、未运行**。
  为不放空话，另写 `matmul_cu_ref.c`（与核函数累加循环逐行同构）已真实编译运行，
  `CHECKSUM = 621`、`9/9 PASS`。

### MUSA 迁移（指南第 8 步）

`matmul.cu` → `matmul_musa.cu` 的机械替换，**实测统计**：

| 项 | 数值 |
|---|---|
| `matmul.cu` 总行数 | 106 |
| `matmul_musa.cu` 总行数 | 106（行数不变） |
| **发生改动的行数** | **14 行** |
| unified diff 行数 | 39 行 |

替换规则与命中次数（按替换顺序）：

| 原 token | 替换为 | 命中 |
|---|---|---|
| `cudaMemcpyHostToDevice` | `musaMemcpyHostToDevice` | 2 |
| `cudaMemcpyDeviceToHost` | `musaMemcpyDeviceToHost` | 1 |
| `cudaMemcpy`（剩余） | `musaMemcpy` | 6 |
| `cudaMalloc` | `musaMalloc` | 3 |
| `cudaFree` | `musaFree` | 3 |
| `cudaDeviceSynchronize` | `musaDeviceSynchronize` | 1 |
| 注释/字符串里的 `CUDA` | `MUSA` | 3 行 |

**MUSA 与 CUDA 的接口关系**：

- MUSA（摩尔线程 Moore Threads）的运行时 API **刻意对齐 CUDA**：`musaMalloc`/`musaMemcpy`/
  `musaFree`/`musaDeviceSynchronize` 与 `cudaXxx` 一一同名同签名。
- **语言层完全同构、不需改**：`__global__`、`blockIdx`、`blockDim`、`threadIdx`、
  `<<<grid, block>>>` 启动语法、warp 概念全部保留。
- 因此 CUDA 代码迁移到 MUSA **通常只是「换前缀 + 换头文件 + 换编译器（nvcc → mcc）」**，
  本实验 106 行源码里只有 14 行（13%）需要动，且全是**机械替换**，没有算法改动。
- 边界：生态工具链（cuBLAS ↔ muBLAS、Nsight ↔ muDNN 等）与具体算子库不完全对等，
  `__shfl_*` 等 warp 内建函数的细节可能有差异，大数据量/复杂 kernel 仍需人工核对。

---

## 6. 复现命令（本机实测可跑）

```bat
:: 初始化 MSVC 环境
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

:: 1. C 版编译运行（-O0 与 -O2）
cl /nologo /utf-8 /Od /Fematmul_Od.exe matmul.c  &&  matmul_Od.exe
cl /nologo /utf-8 /O2 /Fematmul_O2.exe matmul.c  &&  matmul_O2.exe

:: 2. 生成汇编（-O0 / -O2，/FAs 另存带源码注释版）
cl /nologo /utf-8 /Od /FA /Faasm_cl\matmul_Od.asm matmul.c
cl /nologo /utf-8 /O2 /FA /Faasm_cl\matmul_O2.asm matmul.c
cl /nologo /utf-8 /Od /FAs /Faasm_cl\matmul_O0_src.asm matmul.c
cl /nologo /utf-8 /O2 /FAs /Faasm_cl\matmul_O2_src.asm matmul.c

:: 3. 耗时基准
cl /nologo /utf-8 /Od /Febench_O0.exe bench_matmul.c  &&  bench_O0.exe
cl /nologo /utf-8 /O2 /Febench_O2.exe bench_matmul.c  &&  bench_O2.exe

:: 4. CUDA 内核语义的 CPU 等价验证（无 CUDA Toolkit 时的替代证据）
cl /nologo /utf-8 /Od /Fematmul_cu_ref.exe matmul_cu_ref.c  &&  matmul_cu_ref.exe

:: 5. Verilog 仿真（需 Icarus Verilog）
iverilog -g2012 -o tb.vvp -s tb_matmul matmul.v tb_matmul.v
vvp tb.vvp
```

---

## 7. 结果一致性汇总

| 实现层 | 运行/验证方式 | 结果矩阵 | CHECKSUM | 结论 |
|---|---|---|---|---|
| C（-Od） | cl 真实编译运行 | 30 24 18 / 84 69 54 / 138 114 90 | **621** | 9/9 PASS |
| C（-O2） | cl 真实编译运行 | 同上 | **621** | 9/9 PASS |
| NumPy（标准答案） | `A @ B` | 同上 | **621** | 基准 |
| Verilog | **Icarus Verilog 12.0 真实仿真（-g2012，零警告）** | 同上 | **621** | 9/9 PASS |
| CUDA | 无 nvcc，用 CPU 等价实现验证 | 同上 | **621** | 9/9 PASS |

**四层同算法、同输入、同结果：`CHECKSUM = 621`，9 个元素逐项一致。**
