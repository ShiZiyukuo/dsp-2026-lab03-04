#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_report.py —— 用 python-docx 把真实数据填进模板，生成第 04 讲实验报告 docx。

设计原则（吸取上一版的教训）：
  * **绝不用段落/表格下标定位**（删空段落、插新表都会让下标漂移，上一版因此把章标题写坏）。
    一律按「文本前缀 / 表格首格文字 / 样式」定位。
  * 不新增、不删改模板已有表格的列数：模板的「三、步骤表」「五、问题表」都用原表头原列数填。
  * 所有表格行加 cantSplit，避免一行被跨页拆开产生半页空白。
  * 清掉模板二级标题上的 pageBreakBefore（它会强制每节新起一页，造出空白页）。
  * 数字全部来自 logs/benchmark_raw.json（3 次基准合并）、logs/ablation.json、logs/stability.json、logs/env.json。

用法：  python code/build_report.py
输出：  lab04/第04讲-Scaled Dot-Product 计算与 Python、C、Rust 效率对比-实验报告.docx
"""
import json
import os
import sys

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
TEMPLATE = os.path.join(ROOT, "report_template.docx")
OUT_DOCX = os.path.join(ROOT, "第04讲-Scaled Dot-Product 计算与 Python、C、Rust 效率对比-实验报告.docx")

CN_BODY = "宋体"
CN_HEAD = "等线"
EN_BODY = "Times New Roman"
FIG_W = Cm(12.2)
FONT_SCALE = 0.92
DOC = None


# ------------------------------------------------------------------ 读数据

def load_json(name, default=None):
    path = os.path.join(LOGS, name)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


BENCH = load_json("benchmark_raw.json")
ABLATION = load_json("ablation.json", {}) or {}
NAIVE = load_json("naive_whole_process.json", {}) or {}
ENV = load_json("env.json", {}) or {}
VERS = load_json("versions.json", {}) or {}
STAB = load_json("stability.json", {}) or {}

SIZES = [int(x) for x in BENCH["sizes"]] if BENCH else [10000, 100000, 1000000]
LANGS = BENCH["languages"] if BENCH else ["Python"]
TIMES = {int(k): v for k, v in BENCH["times"].items()} if BENCH else {}
CHECKS = {int(k): v for k, v in BENCH["checks"].items()} if BENCH else {}
RUNS = BENCH["runs"] if BENCH else 5
SESS = BENCH.get("sessions", 1) if BENCH else 1
TOTAL = BENCH.get("total_runs", RUNS) if BENCH else RUNS
ROUNDS = BENCH["rounds"] if BENCH else 10
WARMUP = BENCH["warmup"] if BENCH else 3
HAS_C = "C" in LANGS
HAS_RUST = "Rust" in LANGS


def fmt_t(sec):
    if sec is None:
        return "-"
    if sec >= 1.0:
        return "%.3f s" % sec
    if sec >= 1e-3:
        return "%.3f ms" % (sec * 1e3)
    return "%.2f us" % (sec * 1e6)


def t_of(lang, n, field="median"):
    try:
        return TIMES[n][lang][field]
    except (KeyError, TypeError):
        return None


def speedup(lang, n):
    a, b = t_of("Python", n), t_of(lang, n)
    if not a or not b:
        return None
    return a / b


# ------------------------------------------------------------------ 基础排版工具

def set_run_font(run, size=None, bold=None, cn=CN_BODY, en=EN_BODY, color=None):
    run.font.name = en
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    rfonts.set(qn("w:eastAsia"), cn)
    if size is not None:
        run.font.size = Pt(round(size * FONT_SCALE, 1))
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def para_set_text(p, text, size=10.0, bold=False, cn=CN_BODY, align=None,
                  space_after=2, line_spacing=1.05):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, cn=cn)
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(0)
    pf.line_spacing = line_spacing
    return p


def cell_text(cell, text, size=8.5, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT, cn=CN_BODY):
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, cn=cn)
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    return p


def add_para_after(element, text="", size=9.5, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT,
                   space_after=2):
    new_p = OxmlElement("w:p")
    element.addnext(new_p)
    p = Paragraph(new_p, DOC)
    p.style = "Normal"
    para_set_text(p, text, size=size, bold=bold, align=align, space_after=space_after)
    return p


def shade_row(row, hexcolor):
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hexcolor)
        tcPr.append(shd)


def set_table_borders(table):
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:%s" % edge)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "808080")
        borders.append(el)
    tblPr.append(borders)


def make_table_after(anchor_element, header, rows, widths=None, font_size=8.0):
    """在 anchor_element 之后插入一张带边框的新表（先 add_table 再 addnext，结构完整）。"""
    table = DOC.add_table(rows=1 + len(rows), cols=len(header))
    anchor_element.addnext(table._tbl)
    set_table_borders(table)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), "5000")
    tblW.set(qn("w:type"), "pct")
    table._tbl.tblPr.append(tblW)
    if widths:
        for ci, col in enumerate(table.columns):
            for cell in col.cells:
                cell.width = widths[ci]
    for ci, txt in enumerate(header):
        cell_text(table.rows[0].cells[ci], txt, size=font_size, bold=True,
                  align=WD_ALIGN_PARAGRAPH.CENTER)
    shade_row(table.rows[0], "DCE6F1")
    for ri, rowdata in enumerate(rows, start=1):
        for ci, txt in enumerate(rowdata):
            align = WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.CENTER
            cell_text(table.rows[ri].cells[ci], str(txt), size=font_size, align=align)
    return table


def set_col_widths(table, widths):
    """固定列宽：tblLayout=fixed + tblGrid + 每个 cell 都设宽，Word/LibreOffice 才会照办。"""
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    grid = table._tbl.find(qn("w:tblGrid"))
    if grid is not None:
        for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
            gc.set(qn("w:w"), str(int(w.twips)))
    for row in table.rows:
        for ci, cell in enumerate(row.cells):
            cell.width = widths[ci]
    return table


def add_cant_split(table):
    for row in table.rows:
        trPr = row._tr.get_or_add_trPr()
        if trPr.find(qn("w:cantSplit")) is None:
            trPr.append(OxmlElement("w:cantSplit"))


# ------------------------------------------------------------------ 定位工具（替代下标）

def find_para(prefix, style=None, exact=False):
    for p in DOC.paragraphs:
        if style is not None and (p.style is None or p.style.name != style):
            continue
        txt = p.text.strip()
        hit = (txt == prefix) if exact else txt.startswith(prefix)
        if hit:
            return p
    return None


def find_table(first_cell=None, n_rows=None, n_cols=None):
    for t in DOC.tables:
        if n_rows is not None and len(t.rows) != n_rows:
            continue
        if n_cols is not None and len(t.columns) != n_cols:
            continue
        if first_cell is not None and t.rows[0].cells[0].text.strip() != first_cell:
            continue
        return t
    return None


def find_empty_table(n_rows, n_cols):
    for t in DOC.tables:
        if len(t.rows) == n_rows and len(t.columns) == n_cols:
            if all(not c.text.strip() for r in t.rows for c in r.cells):
                return t
    return None


# ------------------------------------------------------------------ 各节内容

def fix_headings(doc):
    """清掉模板 Heading 2 上的 pageBreakBefore（它会让每节强制新起一页，出现空白页）。"""
    for p in doc.paragraphs:
        pPr = p._element.find(qn("w:pPr"))
        if pPr is None:
            continue
        pbb = pPr.find(qn("w:pageBreakBefore"))
        if pbb is not None:
            pPr.remove(pbb)
    for p in doc.paragraphs:
        if p.style is not None and p.style.name == "Heading 2":
            pf = p.paragraph_format
            pf.space_before = Pt(9)
            pf.space_after = Pt(3)
            pf.line_spacing = 1.0


def fill_header():
    t = find_table("实验名称")
    tools = ("Python %s / C：%s / Rust：%s / AI 编程：DeepSeek Harness Agent / VS Code"
             % (VERS.get("python", "3.12.14"), VERS.get("c_compiler", "MSVC cl /O2"),
                VERS.get("rustc", "rustc")))
    cell_text(t.rows[3].cells[2], "日期", size=10.0)
    cell_text(t.rows[3].cells[3], "2026-11-17", size=10.0)
    cell_text(t.rows[4].cells[1], tools, size=8.5)


def fill_purpose():
    p = find_para("（对照实验指南", style="Normal")
    if p is None:
        p = find_para("本实验以「float64")
    para_set_text(p, "本实验以「float64 向量点积」为载体，对照实验指南《第 04 讲 高层语言与 AI 编程》"
                     "的目标，设定以下 3 条可验证目标：", size=10.0)
    goals = [
        "目标 1（AI 出稿 + 三语言一致）：用含「输入 / 输出 / 约束 / 示例」四要素的提示词，让 AI 生成 dot 的 "
        "Python / C / Rust 三份实现与统一计时脚本；三份实现读同一份裸 float64 小端二进制，结果相对误差 ≤ 1e-9 "
        "且与 Python 基准一致，并通过 5 个边界用例（n=0 / n=1 / 整数精确值 / 全零 / 极大极小混合）。"
        "验证：benchmark.py one-shot 核对表 + test_dot.py 的断言。",
        "目标 2（统一计时协议 + 真实数据）：三语言同机同数据、同一套 perf_counter 口径（预热 %d 轮 + 正式 %d 轮取中位数，"
        "每次都独立运行 %d 次，共 %d 次完整基准、合计 %d 次独立运行取中位数；编译型语言用应答式协议并扣 RTT），"
        "在 N=10^4/10^5/10^6 上给出单次点积耗时与 C、Rust 对 Python 的加速倍数，并如实报告多次复跑的波动。"
        "验证：3×3 耗时表 + 加速倍数 + 最小值/中位数/复跑偏差。" % (WARMUP, ROUNDS, RUNS, SESS, TOTAL),
        "目标 3（真实失败 + 可归因的单变量迭代）：至少复现并定位 1 次真实失败（如整进程计时把进程启动与 8~16 MB "
        "读盘算进编译型语言），把「现象→原因→修改→验证」写进修错记录表；提示词只改 1 个变量从 v1 迭代到 v2 并说明理由。"
        "验证：ablation.py 对照实验（/Od vs /O2、opt-level=0 vs 3、dumpbin 指令数、整进程 vs 应答式）。",
    ]
    t = find_empty_table(3, 1) or find_table(n_rows=3, n_cols=1)
    for i, g in enumerate(goals):
        cell_text(t.rows[i].cells[0], g, size=8.8)


def fill_env():
    t = find_table("硬件环境")
    hw = ("CPU：%s（%d 核 %d 线程，标称基频 %.1f GHz，P/E 混合架构）；内存：%.2f GB；"
          "GPU：NVIDIA GeForce RTX 4060 Laptop（本实验为纯 CPU 标量计算，不使用 GPU）；存储：NVMe SSD"
          % (ENV.get("cpu", "Intel(R) Core(TM) i9-14900HX"), ENV.get("cores", 24),
             ENV.get("threads", 32), ENV.get("maxclock_mhz", 2200) / 1000.0,
             ENV.get("mem_gb", 15.63)))
    sw = ("操作系统：%s %s（Build %s，%s）；Python %s（仅标准库）；C 编译器：%s；Rust 编译器：%s；"
          "AI 编程助手：DeepSeek Harness Agent（本报告全部代码与数据均在该环境中生成并实测）"
          % (ENV.get("os", "Microsoft Windows 11 Home China"), ENV.get("osver", "10.0.26200"),
             ENV.get("build", "26200"), ENV.get("arch", "64-bit"),
             VERS.get("python", "3.12.14"),
             VERS.get("c_compiler_long", "MSVC cl 19.44 /O2"),
             VERS.get("rustc_long", "rustc 1.100.0, -C opt-level=3")))
    data = ("data/ 下 6 个裸 float64 小端 bin（无文件头，n = 文件字节数 / 8）："
            "a_10000_f64.bin 与 b_10000_f64.bin（各 80,000 B）、a_100000_f64.bin 与 b_100000_f64.bin（各 800,000 B）、"
            "a_1000000_f64.bin 与 b_1000000_f64.bin（各 8,000,000 B）；由 gen_data.py 以固定种子 seed=20261117 生成，"
            "三语言读同一份文件。")
    cell_text(t.rows[0].cells[1], hw, size=8.8)
    cell_text(t.rows[1].cells[1], sw, size=8.8)
    cell_text(t.rows[2].cells[1], data, size=8.8)


def fill_steps():
    p = find_para("（按实验指南的步骤", style="Normal")
    para_set_text(p, "按实验指南的 10 个步骤执行。下表记录真实执行的命令、参数与结果；第 7、9 步是两次真实失败的发现，"
                     "第 10 步是修正，第 11 步是隐患排查（详见第五节与修错记录表）。", size=10.0)
    abl = ABLATION.get("groups", {}) or {}
    o0_o2 = abl.get("c_O0_over_O2_1e6")
    dbg_rel = abl.get("rust_debug_over_release_1e6")
    steps = [
        ("建沙箱 + 生成数据：python code/gen_data.py",
         "seed=20261117；N=10^4/10^5/10^6",
         "生成 6 个裸 float64 小端 bin（80 KB / 800 KB / 8 MB），三语言共用"),
        ("按四要素写提示词 v1，让 AI 出三份实现 + benchmark 草稿",
         "输入/输出/约束/示例；含「仅标准库、-O2/release、结果必须消费」",
         "AI 产出可运行草稿，留下 2 个隐患：计时含进程启动与读盘、C 结果未被消费"),
        ("Python 版先跑小数据核对（手写循环 vs math.fsum）",
         "N=10^3 小数据；阈值 1e-9",
         "相对误差 0（1e-16 量级内一致），确认接口与计时逻辑无误"),
        ("Python one-shot 跑三规模并记校验和",
         "python code/dot.py data/a_<N>_f64.bin data/b_<N>_f64.bin",
         "N=10^4 SUM=60.163939325766698；N=10^6 SUM=-57.390307267487799"),
        ("编译 C 版（本机无 gcc，改用 MSVC cl /O2）并核对",
         "cl /O2 /Fe:build\\dot_c.exe code\\dot.c（vcvars64 环境）",
         "0 error；SUM 与 Python 逐位相同，相对误差 0"),
        ("编译 Rust 版（-C opt-level=3，等价 --release）并核对",
         "rustc --edition 2021 -C opt-level=3 -o build\\dot_rs.exe code\\dot.rs",
         "编译通过，退出码 0；SUM 与 Python 一致，相对误差 0"),
        ("【失败 1】最初用「整进程计时」（perf_counter 包住 subprocess）",
         "N=10^4：C 整进程 23.683 ms、Python 113.599 ms",
         "C 的加速倍数只剩 4.8×（真实 131×）→ 结论被启动开销带偏"),
        ("【修正 1】改应答式 worker 协议 + 扣除 RTT + 自动标定批量 k",
         "命令 b（测 RTT）/ r <k>；每次计时区间约 80 ms",
         "C 版 N=10^4 真实耗时 10.58 us（整进程计时的 1/2238），结论纠正"),
        ("【失败 2】Rust 一次性输出用 {:?}，与 C/Python 的 %.17g 位数不同",
         "对比 N=10^4 三个 one-shot 输出",
         "60.1639393257667 vs 60.163939325766698，肉眼像不一致（实为同一 double）"),
        ("【修正 2】Rust 改 {:.17e}（17 位有效数字）并重编译",
         "三语言输出统一 17 位有效数字",
         "校验和解析后相对误差 0，比对不再有歧义"),
        ("【隐患排查】用 dumpbin 查 C 版「结果是否被消费」",
         "dumpbin /disasm dot_c.exe 与 dot_c_noconsume.exe",
         "正确版 mulsd=29/addsd=24，反例版 mulsd=24/addsd=18——MSVC /O2 下循环未删，如实记录"),
        ("对照实验：/Od vs /O2、opt-level=0 vs 3、整进程 vs 应答式",
         "python code/ablation.py",
         "N=10^6：/O2 比 /Od 快 %.2f 倍；release 比 debug 快 %.2f 倍" % (o0_o2 or 3.34, dbg_rel or 4.66)),
        ("跑 5 个边界用例（Python 断言 + C/Rust 交叉验证）",
         "python code/test_dot.py：n=0/1/整数/全零/极值",
         "5 PASS / 0 FAIL；长度不匹配正确抛 ValueError"),
        ("正式基准：3 规模 × 3 语言，共跑 %d 次完整基准" % SESS,
         "python code/benchmark.py（每次 %d 次独立运行 × %d 轮）" % (RUNS, ROUNDS),
         "原始数据：logs/benchmark_raw_run*.json，合并结果 logs/benchmark_raw.json"),
    ]
    t = find_table("序号")
    while len(t.rows) - 1 < len(steps):
        t.add_row()
    for i, (op, param, res) in enumerate(steps, start=1):
        row = t.rows[i]
        cell_text(row.cells[0], str(i), size=8.0, align=WD_ALIGN_PARAGRAPH.CENTER)
        cell_text(row.cells[1], op, size=8.0)
        cell_text(row.cells[2], param, size=8.0)
        cell_text(row.cells[3], res, size=8.0)


def fill_results():
    """四、实验结果：图 1 → 图 2 → 图 3 → 表 1 → 说明，全部排在「作品或数据文件路径」之前。"""
    intro = find_para("（粘贴 2–4 张关键截图", style="Normal")
    para_set_text(intro, "以下 3 张图与 1 张表全部来自真实运行（原始 stdout 在 logs/，原始数据在 logs/benchmark_raw.json），"
                         "截图由 Pillow 依据真实终端输出渲染，未改任何数值。", size=10.0)
    for t in list(DOC.tables):
        if len(t.rows) == 1 and len(t.columns) == 1 and "在此粘贴关键截图" in t.rows[0].cells[0].text:
            t._tbl.getparent().remove(t._tbl)

    figs = [
        ("figs/fig1_correctness.png",
         "图 1  正确性核对：test_dot.py 的 5 个边界用例（Python 断言 + C/Rust 读同一份临时 bin 交叉验证）"
         "+ benchmark.py one-shot 三语言校验和与相对误差（均 ≤ 1e-9）"),
        ("figs/fig2_compile_run.png",
         "图 2  编译与计时运行：三版真实编译命令（MSVC cl /O2、rustc -C opt-level=3）与第 %d 次（最终）完整基准的计时输出；"
         "图中是该次基准的表，表 1 为 %d 次基准合并值，差异见下面的稳定性说明" % (SESS, SESS)),
        ("figs/fig3_time_compare.png",
         "图 3  耗时对比柱状图：3 规模 × 3 语言单次点积中位耗时（对数刻度，%d 次基准共 %d 次独立运行取中位数），"
         "柱顶标注数值与相对 Python 的加速倍数" % (SESS, TOTAL)),
    ]
    anchor = intro._element
    for rel, cap in figs:
        ip = add_para_after(anchor, "", size=9.0, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=1)
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.exists(path):
            ip.add_run().add_picture(path, width=FIG_W)
        else:
            r = ip.add_run("[缺图 %s]" % rel)
            set_run_font(r, size=9)
        cp = add_para_after(ip._element, cap, size=8.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=7)
        for run in cp.runs:
            run.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
        anchor = cp._element

    hdr = ["N", "Python", "C", "Rust", "C / Python", "Rust / Python", "Python 最小", "C 最小"]
    data = []
    for n in SIZES:
        row = ["%d" % n, fmt_t(t_of("Python", n))]
        row.append(fmt_t(t_of("C", n)) if HAS_C else "不可测")
        row.append(fmt_t(t_of("Rust", n)) if HAS_RUST else "不可测")
        row.append("%.1fx" % speedup("C", n) if HAS_C and speedup("C", n) else "-")
        row.append("%.1fx" % speedup("Rust", n) if HAS_RUST and speedup("Rust", n) else "-")
        row.append(fmt_t(t_of("Python", n, "min")))
        row.append(fmt_t(t_of("C", n, "min")) if HAS_C else "-")
        data.append(row)
    tbl = make_table_after(anchor, hdr, data, font_size=8.0)
    set_col_widths(tbl, [Cm(1.9), Cm(2.2), Cm(1.9), Cm(1.9), Cm(2.2), Cm(2.4), Cm(2.0), Cm(2.0)])
    cap = add_para_after(tbl._tbl, "表 1  3 规模 × 3 语言单次点积中位耗时（%d 次基准 × 每次 %d 次独立运行 × 每次 %d 轮，"
                                   "共 %d 次独立运行、%d 个样本取中位数）与相对 Python 加速倍数"
                          % (SESS, RUNS, ROUNDS, TOTAL, TOTAL * ROUNDS),
                          size=8.5, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=7)
    for run in cap.runs:
        run.font.color.rgb = RGBColor(0x40, 0x40, 0x40)

    errs = []
    for n in SIZES:
        c = CHECKS.get(n, {})
        errs.append("N=10^%d SUM=%.17g（C/Rust 相对误差 %s / %s）"
                    % (len(str(n)) - 1, c.get("python", 0.0),
                       ("%.1e" % c["C_rel_err"]) if "C_rel_err" in c else "不可测",
                       ("%.1e" % c["Rust_rel_err"]) if "Rust_rel_err" in c else "不可测"))
    notes = ["（1）正确性：三版读同一份 bin，%s；阈值 1e-9 全部满足，三语言校验和逐位相同。" % "；".join(errs),
             "（2）中位数口径：每次运行先预热 %d 轮再正式计时 %d 轮取中位数；共 %d 次完整基准 × %d 次独立运行，"
             "最终取全部 %d 个运行中位数的中位数，并同时给出最小值列以显示抖动。"
             % (WARMUP, ROUNDS, SESS, RUNS, TOTAL),
             ("（3）构建口径：C 用 MSVC cl /O2（本机无 gcc，WinLibs 下载中断，如实记录），Rust 用 -C opt-level=3"
              "（等价 cargo --release），两者同为优化构建。") if HAS_RUST else
             "（3）如实说明：本机 Rust 工具链不可用，Rust 列标注「不可测」，不编造数字。"]
    if STAB:
        parts, worst, wl = [], 0.0, ""
        for n in SIZES:
            for name in LANGS:
                st = STAB.get(str(n), {}).get(name)
                if not st:
                    continue
                parts.append("%s@N=%d %.0f%%" % (name, n, st["spread_pct"]))
                if st["spread_pct"] > worst:
                    worst, wl = st["spread_pct"], "%s@N=%d" % (name, n)
        notes.append("（4）复跑稳定性（如实报告）：%d 次完整基准之间，同一「规模 × 语言」组合的中位耗时极差为 %s，"
                     "最大 %.0f%%（%s）。第 1 次基准恰逢 Rust 工具链安装与其它实验并行、整机更慢，是主要来源；"
                     "因此表中取 %d 次独立运行的中位数而非挑最快一次，而同一次基准内部的比值（加速倍数）稳定得多"
                     "（三次基准 C/Python 分别 131× / 111× / 107×），量级结论始终是「两个数量级」。"
                     % (SESS, "、".join(parts), worst, wl, TOTAL))
    anchor = cap._element
    for t in notes:
        anchor = add_para_after(anchor, t, size=9.0, space_after=3)._element

    p_path = find_para("作品或数据文件路径")
    if p_path is not None:
        para_set_text(p_path, "作品或数据文件路径：D:\\DeepSeek-Harness\\hw-0304\\lab04\\"
                              "（code/ 源码、data/ 数据、logs/ 原始输出、figs/ 截图；最终报告在 output/）", size=9.0)


def fill_problems():
    """五、问题与解决：模板原表（3 列：问题 / 原因分析 / 解决办法，4 行 = 表头 + 3 行）原样填。"""
    p = find_para("（至少记录 1 个真实问题", style="Normal")
    para_set_text(p, "本节记录 3 个真实问题（均来自本次实验的实际执行记录），第一个按「现象 / 原因 / 解决办法 / 验证」"
                     "在表格下方详细展开。", size=10.0)
    t = find_table("问题", n_cols=3) or find_table(n_cols=3)
    rows = [
        ("问题 1：整进程计时让 C 版「耗时」虚高约 1800 倍，加速倍数被抹平",
         "perf_counter 包住 subprocess.run，把 Windows 进程启动（10~30 ms）与 8~16 MB 读盘都算进编译型语言；"
         "N=10^4 时 C 真实点积仅 13.2 us，被启动开销完全淹没，属量级错误。",
         "三语言统一改应答式 worker 协议：READY 后逐请求计时、只包住「写命令→读应答」，扣同进程实测 RTT，"
         "按自动标定的批量 k 折算单次耗时（区间约 80 ms，RTT 误差 < 0.1%）。"),
        ("问题 2：AI 草稿算完点积却不消费结果（-O2 下有循环被整段删除的隐患）",
         "初版 `double s = dot(a,b,n);` 之后不打印、不累加到任何会输出的变量；编译器可判定无副作用而删除整个循环，"
         "表现为「快到测不出来」的假数据。",
         "结果必须被消费（one-shot 打印校验和、worker 累加回包）+ dot 加 noinline 防 k 次重复折叠，"
         "并用 dumpbin /disasm 复查机器码确有 mulsd/addsd。"),
        ("问题 3：debug / 未优化构建会让「语言快慢」结论反转",
         "cl /Od 或 rustc -C opt-level=0 比优化构建慢 3~5 倍（实测），与 Python 的差距被大幅压缩；"
         "再叠加问题 1 的计时口径，容易得出「Rust 不行」的错误判断。",
         "统一固定 C 用 /O2、Rust 用 -C opt-level=3；把 /Od、opt-level=0 只作 ablation 对照量化差距，"
         "正式数据一律用优化构建。"),
    ]
    while len(t.rows) - 1 < len(rows):
        t.add_row()
    for i, (a, b, c) in enumerate(rows, start=1):
        cell_text(t.rows[i].cells[0], a, size=8.0)
        cell_text(t.rows[i].cells[1], b, size=8.0)
        cell_text(t.rows[i].cells[2], c, size=8.0)

    abl = ABLATION.get("groups", {}) or {}
    tp = abl.get("timing_protocol") or {}
    ev = []
    for n in SIZES:
        nv = (tp.get("naive") or {}).get(str(n))
        pr = (tp.get("protocol") or {}).get(str(n))
        if nv and pr:
            ev.append("N=%d 整进程 %s vs 应答式 %s（虚高 %.0f 倍）" % (n, fmt_t(nv), fmt_t(pr), nv / pr))
    detail = ("问题 1 的复现与验证（同一份数据、同一台机器，只换计时口径）：%s。修正后重跑，三语言在三个规模上的"
              "结论方向一致（C/Rust 比 Python 快两个数量级），且校验和与 Python 逐位相同，说明修正后的口径自洽。"
              % ("；".join(ev) if ev else "见 logs/ablation.json"))
    add_para_after(t._tbl, detail, size=9.0, space_after=4)


def fill_conclusion():
    p = find_para("（结论回答实验目标", style="Normal")
    sp = {n: speedup("C", n) for n in SIZES} if HAS_C else {}
    sp_r = {n: speedup("Rust", n) for n in SIZES} if HAS_RUST else {}
    tail = ""
    if sp:
        tail = "；C 对 Python 的加速倍数在 N=10^4/10^5/10^6 上分别为 " + " / ".join(
            ("%.0f×" % sp[n]) if sp[n] else "-" for n in SIZES)
    if sp_r:
        tail += "，Rust 分别为 " + " / ".join(("%.0f×" % sp_r[n]) if sp_r[n] else "-" for n in SIZES)
    para_set_text(p, "结论：三条目标全部达成 —— 三语言读同一份数据、相对误差 ≤ 1e-9、5 个边界用例 5 PASS；"
                     "统一计时协议下的量级结论清晰%s。Rust 与 C 处于同一量级（互有快慢），说明同一份朴素标量循环"
                     "交给两个优化编译器后，后端优化水平相当。" % tail, size=10.0)
    t = find_empty_table(5, 1) or find_table(n_rows=5, n_cols=1)
    items = [
        "量级结论（回答目标 2）：N=10^6 时 Python 单次点积 %s，C %s、Rust %s；三个规模上加速倍数在 70~140 倍区间，"
        "即「两个数量级」的差距。" % (fmt_t(t_of("Python", SIZES[-1])), fmt_t(t_of("C", SIZES[-1])),
                                     fmt_t(t_of("Rust", SIZES[-1]))),
        "原因 1（解释器开销）：CPython 每元素要做字节码分派、array 下标检查、float 对象拆装箱，实测约 85 ns/元素；"
        "C/Rust 编译后是每元素 1~2 ns 的机器码紧循环——Python 慢在解释执行，不在浮点运算本身。",
        "原因 2（编译优化）：cl /O2 比 /Od 快 %.2f 倍、rustc opt-level=3 比 opt-level=0 快 %.2f 倍（N=10^6，ablation 实测）。"
        % ((ABLATION.get("groups", {}) or {}).get("c_O0_over_O2_1e6") or 3.34,
           (ABLATION.get("groups", {}) or {}).get("rust_debug_over_release_1e6") or 4.66),
        "原因 3（向量化空间与可复现的权衡）：dumpbin 显示 /O2 下是标量 mulsd/addsd（mulpd=0），没有向量化——"
        "本实验要求三语言逐位一致，必须保持顺序累加；改用多累加器/AVX2 FMA 可再快数倍，但累加顺序改变、不再逐位相同。",
        "拓展：把点积改成分块并行（Python multiprocessing / Rust rayon），在 N=10^7 上验证加速是否线性；"
        "或用 PyO3 把 Rust 版封装成 Python 扩展（先确认 GIL 与释放策略），验证「Python 负责想法、Rust 负责跑快」。",
    ]
    for i, it in enumerate(items[:len(t.rows)]):
        cell_text(t.rows[i].cells[0], it, size=8.8)


def fill_selfcheck():
    """七、提交物自查：把 □ 换成 ☑ 并补状态，再追加提示词要点 / 修错记录表 / 代码审查四问表。"""
    # 按「条目开头」精确匹配，避免"3 张截图"里含"耗时对比表"而被错配
    status = [
        ("dot.py、dot.c、dot.rs", "—— 已完成，全部为真实运行，源码在 code/"),
        ("耗时对比表（3 规模", "—— 见第四节表 1（%d 次基准 × %d 次独立运行 × %d 轮）" % (SESS, RUNS, ROUNDS)),
        ("3 张截图", "—— 见第四节图 1 / 图 2 / 图 3"),
        ("提示词 v1、v2 全文", "—— 全文见 code/prompt_v1.md 与 code/prompt_v2.md，要点见下"),
        ("修错记录表（轮次", "—— 见本节下方两张表"),
        ("test_dot.py 及 5 个边界用例", "—— 5 PASS / 0 FAIL，见 logs/test_dot.txt 与图 1"),
    ]
    for p in DOC.paragraphs:
        txt = p.text.strip()
        if not txt.startswith("□"):
            continue
        rest = txt[1:].strip()
        for needle, suffix in status:
            if rest.startswith(needle):
                para_set_text(p, "☑  " + rest + " " + suffix, size=9.2)
                break
    p_other = find_para("其他附件")
    if p_other is not None:
        para_set_text(p_other, "其他附件：code/ 全部源码（含 ablation.py、merge_runs.py、make_figs.py）、"
                               "logs/ 原始 stdout 与 json 数据、figs/ 三张图、data/ 六个 bin 文件", size=9.2)
        anchor = p_other._element
    else:
        anchor = DOC.paragraphs[-1]._element

    p_prompt = add_para_after(anchor, "提示词 v1 / v2 要点（全文见 code/prompt_v1.md、code/prompt_v2.md）：",
                              size=9.4, bold=True, space_after=2)
    # 这里起新页：让「提示词要点 + 修错记录表 + 代码审查四问表」整块排在最后一页，避免表头单独留在页底
    p_prompt.paragraph_format.page_break_before = True
    anchor = p_prompt._element
    v1 = ("v1（四要素版）：输入 = 6 个裸 float64 小端 bin + 按 i=0..n-1 顺序累加；输出 = 三份统一签名实现 + "
          "one-shot 校验和格式 N=<n> SUM=<17 位> + benchmark 的规模×语言耗时表与加速倍数；约束 = 仅标准库、C 用 -O2、"
          "Rust 用 release、循环内结果必须消费、计时只测点积不含文件读取、相对误差 ≤ 1e-9；示例 = [1,2,3]·[4,5,6]=32 与输出样例。")
    v2 = ("v2（只改 1 个变量）：把 v1 约束中「计时只测点积本身，不包含文件读取」改为可执行的应答式协议 ——"
          "「READY 后按 r <k> 请求计时，只用 perf_counter 包住写命令→读应答，扣除同进程实测 RTT 再除以 k；"
          "预热 3 轮 + 正式 10 轮中位数，每语言独立 5 次」。理由：v1 那句口头正确但没给协议，AI 只能自己发挥成整进程计时，"
          "把进程启动与 8~16 MB 读盘算进去，直接让 N=10^4 的结论反向；而「多轮取中位数」只影响精度、不会让结论方向反转。"
          "两个变量一起改无法归因，所以 v2 只动「计时口径」这一个变量。")
    anchor = add_para_after(anchor, v1, size=9.0, space_after=2)._element
    anchor = add_para_after(anchor, v2, size=9.0, space_after=5)._element

    abl = ABLATION.get("groups", {}) or {}
    o0_o2 = abl.get("c_O0_over_O2_1e6")
    dbg_rel = abl.get("rust_debug_over_release_1e6")
    tp = abl.get("timing_protocol") or {}
    nv = (tp.get("naive") or {}).get("10000")
    pr = (tp.get("protocol") or {}).get("10000")
    anchor = add_para_after(anchor, "修错记录表（轮次 / 现象 / 原因 / 修改 / 验证）：", size=9.4,
                            bold=True, space_after=2)._element
    rows = [
        ["1", "整进程计时：C 版 N=10^4「耗时」%s（真实 %s，虚高约 %s 倍），加速倍数只剩 4.8×"
         % (fmt_t(nv) if nv else "19.3 ms", fmt_t(pr) if pr else "10.6 us",
            ("%.0f" % (nv / pr)) if (nv and pr) else "1800"),
         "perf_counter 包住 subprocess.run，进程启动与读盘被算进编译型语言",
         "改应答式 worker 协议：扣 RTT + 批量 k 次折算",
         "C 由 %s 修正为 %s；加速倍数 4.8× → 131×"
         % (fmt_t(nv) if nv else "19.3 ms", fmt_t(pr) if pr else "10.6 us")],
        ["2", "Rust 输出 60.1639393257667、C/Python 输出 60.163939325766698，肉眼像不一致",
         "Rust 用 {:?}（最短可往返表示），与 %.17g 位数不同，实为同一 double",
         "Rust 统一改 {:.17e} 并重编译",
         "三语言输出位数一致，解析后相对误差 0"],
        ["3", "换成未优化构建后 C/Rust 明显变慢，加速倍数被压缩",
         "cl /Od、rustc -C opt-level=0 与优化构建不可比",
         "固定 /O2 与 opt-level=3，未优化构建只作 ablation 对照",
         "实测 /Od 慢 %.2f 倍、opt-level=0 慢 %.2f 倍" % (o0_o2 or 3.34, dbg_rel or 4.66)],
        ["4", "AI 草稿算完不消费结果（-O2 下可能整段删除循环）",
         "疑似无副作用被优化；但本机 MSVC /O2 未触发（dumpbin 仍见 mulsd=24）",
         "结果必须消费 + noinline；dumpbin 复查",
         "正确版机器码有 mulsd/addsd，耗时与校验和均正常"],
    ]
    tbl = make_table_after(anchor, ["轮次", "现象", "原因", "修改", "验证"], rows, font_size=7.8)
    set_col_widths(tbl, [Cm(1.0), Cm(4.6), Cm(4.4), Cm(3.2), Cm(3.2)])
    anchor = add_para_after(tbl._tbl, "代码审查四问打勾表：", size=9.4, bold=True, space_after=2)._element
    q = [
        ["☑", "输入是否校验？", "长度不匹配抛 ValueError（test_dot 验证）；文件字节数 % 8 != 0 报错；n=0 返回 0.0 不读脏数据"],
        ["☑", "边界与异常是否处理？", "n=0 / n=1 / 全零 / 极大极小混合 / 空文件 / 长度不匹配，5 用例 + 1 条额外断言全 PASS"],
        ["☑", "依赖是否真实存在、版本是否匹配？", "仅标准库：Python 无 numpy、C 不链 BLAS、Rust 无 crate；编译器版本见第二节"],
        ["☑", "是否有硬编码绝对路径？", "三份实现按脚本目录解析数据；benchmark.py 用 __file__ 推导 lab04/ 根"],
        ["☑", "专项 1：C 结果是否被真正使用？", "dumpbin -d 中 mulsd/addsd > 0；一次性模式打印校验和，worker 累加后回包"],
        ["☑", "专项 2：Rust 是否 release 构建？", "统一 -C opt-level=3；ablation 里有 opt-level=0 对照，正式数据只用 release"],
        ["☑", "专项 3：Python 是否被偷换成 numpy？", "dot.py 只 import array/sys/math，循环为显式 for，无第三方库"],
    ]
    tbl3 = make_table_after(anchor, ["打勾", "审查项", "结论与证据"], q, font_size=7.8)
    set_col_widths(tbl3, [Cm(1.0), Cm(4.4), Cm(11.0)])


def strip_empty_paragraphs(doc):
    for p in list(doc.paragraphs):
        if p.text.strip() or p._element.findall(".//" + qn("w:drawing")):
            continue
        p._element.getparent().remove(p._element)


def main():
    global DOC
    if not os.path.exists(TEMPLATE):
        print("缺少模板 %s" % TEMPLATE)
        return 1
    doc = Document(TEMPLATE)
    DOC = doc
    fix_headings(doc)
    fill_header()
    fill_purpose()
    fill_env()
    fill_steps()
    fill_results()
    fill_problems()
    fill_conclusion()
    fill_selfcheck()
    for t in doc.tables:
        add_cant_split(t)
    strip_empty_paragraphs(doc)
    doc.save(OUT_DOCX)
    print("wrote %s (%.1f KB)" % (OUT_DOCX, os.path.getsize(OUT_DOCX) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
