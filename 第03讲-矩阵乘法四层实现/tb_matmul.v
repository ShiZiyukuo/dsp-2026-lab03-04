/*
 * 第03讲 matmul.v 的 testbench
 * 用与 matmul.c 完全相同的 A、B 测试数据，检查输出 Y 是否逐项等于 C 版结果。
 * 期望值（与 matmul.c 的 REF 一致）：
 *   C = { 30,  24,  18,
 *         84,  69,  54,
 *       138, 114,  90 }   校验和 621（NumPy A@B 求得，row和 72+207+342）
 */
`timescale 1ns / 1ps

module tb_matmul;

    localparam N = 3;

    reg  [N*N*8-1:0]  A;
    reg  [N*N*8-1:0]  B;
    wire [N*N*32-1:0] Y;

    integer i, j;
    integer errors;
    reg [63:0] checksum;   /* 用 reg[63:0] 而非 SystemVerilog 的 longint，保证 Verilog-2001 可编译 */
    reg [31:0] got;
    reg [31:0] ref_c [0:8];   /* 原名 ref 是 SystemVerilog 保留字，-g2012 下会语法错，故改名 */

    /* 被测模块 */
    matmul #(.N(N)) dut (
        .A (A),
        .B (B),
        .Y (Y)
    );

    /* 把 8bit 元素写进扁平向量的第 idx 个槽 */
    task set_a; input integer idx; input [7:0] v;
        begin A[idx*8 +: 8] = v; end
    endtask
    task set_b; input integer idx; input [7:0] v;
        begin B[idx*8 +: 8] = v; end
    endtask
    function [31:0] get_y; input integer idx;
        begin get_y = Y[idx*32 +: 32]; end
    endfunction

    initial begin
        $dumpfile("tb_matmul.vcd");
        $dumpvars(0, tb_matmul);

        /* 标准答案 */
        ref_c[0]=30; ref_c[1]=24; ref_c[2]=18;
        ref_c[3]=84; ref_c[4]=69; ref_c[5]=54;
        ref_c[6]=138;ref_c[7]=114;ref_c[8]=90;

        /* ---- 输入 A = 1..9, B = 9..1（与 matmul.c 完全相同）---- */
        set_a(0,1);  set_a(1,2);  set_a(2,3);
        set_a(3,4);  set_a(4,5);  set_a(5,6);
        set_a(6,7);  set_a(7,8);  set_a(8,9);

        set_b(0,9);  set_b(1,8);  set_b(2,7);
        set_b(3,6);  set_b(4,5);  set_b(5,4);
        set_b(6,3);  set_b(7,2);  set_b(8,1);

        #10;  /* 组合逻辑，等 10ns 稳定 */

        $display("=== Verilog 组合逻辑仿真 matmul (N=%0d) ===", N);
        $display("A = 1 2 3 / 4 5 6 / 7 8 9");
        $display("B = 9 8 7 / 6 5 4 / 3 2 1");

        $write("Y = ");
        for (i = 0; i < N; i = i + 1) begin
            $write("[");
            for (j = 0; j < N; j = j + 1) begin
                got = get_y(i*N + j);
                $write(" %0d", got);
            end
            $write(" ]");
            if (i < N-1) $write("  ");
        end
        $display("");

        /* ---- 逐项比对 ---- */
        errors = 0;
        checksum = 0;
        $display("--- 与 C 版结果逐项比对 ---");
        for (i = 0; i < N; i = i + 1) begin
            for (j = 0; j < N; j = j + 1) begin
                got = get_y(i*N + j);
                checksum = checksum + got;
                if (got === ref_c[i*N + j])
                    $display("  Y[%0d][%0d] = %4d  REF = %4d  PASS", i, j, got, ref_c[i*N+j]);
                else begin
                    $display("  Y[%0d][%0d] = %4d  REF = %4d  FAIL", i, j, got, ref_c[i*N+j]);
                    errors = errors + 1;
                end
            end
        end

        $display("Y_FLAT = %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                 get_y(0),get_y(1),get_y(2),get_y(3),get_y(4),
                 get_y(5),get_y(6),get_y(7),get_y(8));
        $display("CHECKSUM = %0d", checksum);

        if (errors == 0)
            $display("RESULT: 9/9 PASS  ==> ALL PASS（与 C 版 CHECKSUM=621 一致）");
        else
            $display("RESULT: %0d errors  ==> MISMATCH", errors);

        $finish;
    end

endmodule
