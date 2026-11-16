/*
 * 第03讲 矩阵乘法四层实现 —— 第 3 层：Verilog（generate + genvar 组合逻辑）
 *
 * 规格：parameter N = 3，Y = A x B，全部为组合逻辑（assign 直接写出乘加）
 *
 * 为什么必须用 generate：
 *   Verilog 里数组下标**不能是变量**（`A[i][k]` 中 i/k 是循环变量会被综合器拒绝），
 *   所以 C 语言那种 for 循环写法在 Verilog 里不成立。
 *   generate + genvar 是**编译期/展开期**的循环：循环体在展开时被复制 N*N 份，
 *   每一份的 i、j、k 都替换成常数，于是下标都成了常数 → 合法且可综合。
 *   这正是「Verilog 的并行」与「C 的串行」的接口边界。
 *
 * 端口打包：
 *   A、B、Y 用扁平向量，元素 (i,j) 位于比特 [ (i*N+j)*8 +: 8 ]（行优先）。
 *   避免二维数组端口这个不可综合的写法。
 *
 * 位宽：
 *   元素 8bit 有符号，乘积 32bit；每个 C[i][j] 是 3 个乘积相加，
 *   3 * 255 * 255 = 195075 < 2^18，32bit 绝对够。
 */
`timescale 1ns / 1ps

/* 单个 8x8 有符号乘法器：generate 会把它例化 N*N*N = 27 次 */
module mul8s (
    input  wire signed [7:0]  a,
    input  wire signed [7:0]  b,
    output wire signed [31:0] p
);
    assign p = a * b;
endmodule

module matmul #(
    parameter N = 3            // 矩阵阶数，本实验固定 3
) (
    input  wire [N*N*8-1:0]   A,   // N x N 个 8bit 元素，行优先
    input  wire [N*N*8-1:0]   B,   // N x N 个 8bit 元素，行优先
    output wire [N*N*32-1:0]  Y    // N x N 个 32bit 结果，行优先
);

    genvar i, j, k;

    /* 乘积中间结果：模块级扁平整型数组，下标在 generate 展开后是常数 */
    wire signed [31:0] prod [0:N*N*N-1];
    /* 每个 C[i][j] 的累加和 */
    wire signed [31:0] acc  [0:N*N-1];

    generate
        for (i = 0; i < N; i = i + 1) begin : GEN_ROW
            for (j = 0; j < N; j = j + 1) begin : GEN_COL
                for (k = 0; k < N; k = k + 1) begin : GEN_K
                    /* 关键：例化乘法器。下标 (i*N+j)*N+k 展开后是常数 */
                    mul8s u_mul (
                        .a (A[(i*N + k)*8 +: 8]),
                        .b (B[(k*N + j)*8 +: 8]),
                        .p (prod[(i*N + j)*N + k])
                    );
                end

                /*
                 * 组合逻辑相加。assign 是**并发**赋值，三条加法同时成立，
                 * 书写顺序不代表执行顺序 —— 这也是 Verilog 与 C 最本质的差别。
                 * 3 个乘积相加用两级加法树，深度 log2(3)≈2。
                 */
                assign acc[i*N + j] = prod[(i*N + j)*N + 0]
                                    + prod[(i*N + j)*N + 1]
                                    + prod[(i*N + j)*N + 2];

                assign Y[(i*N + j)*32 +: 32] = acc[i*N + j];
            end
        end
    endgenerate

endmodule
