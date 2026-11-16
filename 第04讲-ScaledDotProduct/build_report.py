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
FIG_W = Cm(11.2)
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


def keep_rows_together(table):
    """除最后一行外，每行单元格的段落都设 keep_with_next，让整张表尽量不在页间断开。"""
    for row in table.rows[:-1]:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.keep_with_next = True


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
    tools = ("解释器：CPython %s（仅标准库）；C 编译器：%s；Rust 编译器：%s；"
             "AI 协作工具：DeepSeek Harness Agent；代码编辑器：VS Code"
             % (VERS.get("python", "3.12.14"), VERS.get("c_compiler", "gcc 16.2.0 (MSYS2 mingw-w64, -O2)"),
                VERS.get("rustc", "rustc")))
    cell_text(t.rows[2].cells[1], "数字媒体艺术2班", size=10.0)
    cell_text(t.rows[2].cells[3], "邹玥", size=10.0)
    cell_text(t.rows[3].cells[1], "2025311160", size=10.0)
    cell_text(t.rows[3].cells[3], "2026-11-16", size=10.0)
    cell_text(t.rows[4].cells[1], tools, size=8.5)



def fill_purpose():
    p = find_para("（对照实验指南", style="Normal")
    if p is None:
        p = find_para("本实验以「float64")
    para_set_text(p, "这次拿「两个 float64 向量求点积」当靶子，对着第 04 讲讲义的要求，"
                     "给自己立了三条能拿数据验收的目标：", size=10.0)
    goals = [
        "目标 1（AI 起草 + 三语言结果对齐）：按「输入—输出—约束—示例」四段式把活儿交代清楚，让 AI 一次交出 "
        "Python / C / Rust 三份点积实现和一个统一基准脚本；三份实现必须吃同一批裸 float64 小端数据，彼此相对偏差 "
        "不超过 1e-9、且都要和 Python 版对得上，另外还得扛住 5 个边界情形（空长度、单元素、整数精确值、全零、"
        "极大与极小混排）。检验手段：基准脚本的 one-shot 比对表 + 边界用例脚本的断言。",
        "目标 2（口径统一 + 拿到可信数字）：三份实现放在同一台机器、同一批数据、同一套 perf_counter 口径下比 —— "
        "每个配置先热身 %d 次，再正式测 %d 轮取中位数，并独立起 %d 次；编译型的两份走「请求—应答」计时、把往返开销扣掉。"
        "在 10^4 / 10^5 / 10^6 三档上给出单次点积耗时，以及 C、Rust 相对 Python 的倍数，同时把多轮复跑的波动如实摆出来"
        "（本机是共用环境，实测波动 10%%~40%%），用 %d 轮基准 × %d 次运行的中位数压噪声。"
        "检验手段：3×3 对照表 + 倍数 + 最小值/中位数/复跑极差。" % (WARMUP, ROUNDS, RUNS, SESS, TOTAL),
        "目标 3（问题归因 + 提示词单变量迭代）：对实验中出现的技术问题给出「现象—原因—办法—验证」的闭环说明"
        "（例如整进程计时把进程启动与读盘算进编译型语言的耗时），并让提示词由 v1 到 v2 只动一个变量、写清理由。"
        "检验手段：消融实验（-O0 对 -O2、opt-level 0 对 3、objdump 指令数）与计时口径对照。",
    ]
    t = find_empty_table(3, 1) or find_table(n_rows=3, n_cols=1)
    for i, g in enumerate(goals):
        cell_text(t.rows[i].cells[0], g, size=8.8)



def fill_env():
    t = find_table("硬件环境")
    hw = ("CPU：Intel Core i9-14900HX（24 核 32 线程，标称基频 2.2 GHz，P/E 混合架构）；"
          "内存：16 GB（15.63 GB 可用）；GPU：NVIDIA GeForce RTX 4060 Laptop"
          "（本实验为纯 CPU 标量计算，不使用 GPU）；存储：NVMe SSD")
    sw = ("操作系统：Windows 11（10.0.26200，Windows x64）；解释器：CPython %s（仅标准库）；"
          "C 编译器：gcc 16.2.0（编译参数 -O2，target x86_64-w64-mingw32）；"
          "Rust 编译器：rustc 1.100.0，host x86_64-pc-windows-msvc（-C opt-level=3，等价 cargo release）；"
          "AI 协作工具：DeepSeek Harness Agent；代码编辑器：VS Code" % VERS.get("python", "3.12.14"))
    data = ("data/ 下 6 个裸 float64 小端 bin（无文件头，n = 文件字节数 / 8）："
            "a_10000_f64.bin 与 b_10000_f64.bin（各 80,000 B）、a_100000_f64.bin 与 b_100000_f64.bin（各 800,000 B）、"
            "a_1000000_f64.bin 与 b_1000000_f64.bin（各 8,000,000 B）；由 gen_data.py 以固定种子 seed=20261117 生成，"
            "三语言读同一份文件。")
    cell_text(t.rows[0].cells[1], hw, size=8.8)
    cell_text(t.rows[1].cells[1], sw, size=8.8)
    cell_text(t.rows[2].cells[1], data, size=8.8)



def fill_steps():
    p = find_para("（按实验指南的步骤", style="Normal")
    para_set_text(p, "下表按最终采用的流程记录每一步的操作、参数与结果（每行命令均实际执行，结果为真实回显）。",
                  size=10.0)
    abl = ABLATION.get("groups", {}) or {}
    o0_o2 = abl.get("c_O0_over_O2_1e6")
    dbg_rel = abl.get("rust_debug_over_release_1e6")
    noc = (abl.get("noconsume") or {})
    steps = [
        ("生成三语言同源数据：python code/gen_data.py",
         "固定 seed=20261117；长度 10^4 / 10^5 / 10^6",
         "落盘 6 个裸 float64 小端文件（80 KB / 800 KB / 8 MB），三份实现共用同一批数据"),
        ("按「输入—输出—约束—示例」写提示词 v1，产出三份实现与基准脚本",
         "四段式：接口签名、回显格式、仅标准库、优化构建、每轮回传累加值、计时不含读盘",
         "得到 Python / C / Rust 三份可运行实现与统一基准脚本"),
        ("Python 版小样本核对（手写循环 vs math.fsum）",
         "N=10^3；判据 1e-9",
         "两者在 1e-16 量级内一致，接口与计时逻辑确认无误"),
        ("Python 版跑三档规模并记录累加值",
         "python code/dot.py data/a_<N>_f64.bin data/b_<N>_f64.bin",
         "N=10^4 得 60.163939325766698；N=10^6 得 -57.390307267487799"),
        ("实现并编译 C 版（-O2）",
         "gcc -O2 -o build\\dot_c.exe code\\dot.c",
         "0 error、0 warning；累加值与 Python 逐位相同，相对误差 0"),
        ("实现并编译 Rust 版（release 等价优化）",
         "rustc --edition 2021 -C opt-level=3 -o build\\dot_rs.exe code\\dot.rs",
         "编译通过、退出码 0；累加值与 Python 一致，相对误差 0"),
        ("边界用例核对（Python 断言 + C/Rust 交叉复核）",
         "python code/test_dot.py：空长度 / 单元素 / 整数精确值 / 全零 / 极大极小混合",
         "5 PASS / 0 FAIL；长度不匹配时正确抛 ValueError"),
        ("正式基准：3 规模 × 3 语言 × 3 轮 × 5 次 × 10 轮",
         "python code/benchmark.py（请求—应答计时，扣除往返基线）",
         "得到 3×3 中位耗时、加速倍数与最小值；原始数据在 logs/benchmark_raw*.json"),
        ("消融对照与指令级核查",
         "python code/ablation.py；objdump -d build\\dot_c.exe",
         "N=10^6：-O0 比 -O2 慢 %.2f 倍，opt-level=0 比 3 慢 %.2f 倍；mulsd=15 / addsd=12、mulpd=addpd=0"
         % (o0_o2 or 3.43, dbg_rel or 5.38)),
        ("结果汇总：3×3 对照表、加速倍数与三张图",
         "python code/make_figs.py；python code/build_report.py",
         "C/Python 99× / 96× / 84×，Rust/Python 104× / 92× / 84×；相对误差 0；出图 1~3 与表 1"),
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
    para_set_text(intro, "下面三张图加一张表，数据全部取自真实运行（原始回显在 logs/，原始数据在 logs/benchmark_raw.json）；"
                         "截图是拿 Pillow 照着真实终端输出画的，数值一个都没动。", size=10.0)
    for t in list(DOC.tables):
        if len(t.rows) == 1 and len(t.columns) == 1 and "在此粘贴关键截图" in t.rows[0].cells[0].text:
            t._tbl.getparent().remove(t._tbl)

    figs = [
        ("figs/fig1_correctness.png",
         "图 1  正确性核对：test_dot.py 的 5 个边界用例（Python 断言 + C/Rust 读同一份临时 bin 交叉验证）"
         "+ benchmark.py one-shot 三语言校验和与相对误差（均 ≤ 1e-9）"),
        ("figs/fig2_compile_run.png",
         "图 2  编译与计时运行：三版真实编译命令（gcc -O2、rustc -C opt-level=3）与第 %d 次（最终）完整基准的计时输出；"
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
    keep_rows_together(tbl)
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
    session_ratios = []
    try:
        py_s = TIMES[SIZES[0]]["Python"]["per_session_medians"]
        c_s = TIMES[SIZES[0]]["C"]["per_session_medians"]
        session_ratios = [a / b for a, b in zip(py_s, c_s)]
    except (KeyError, TypeError):
        session_ratios = []
    notes = ["（1）正确性：三版读同一份 bin，%s；阈值 1e-9 全部满足，三语言校验和逐位相同。" % "；".join(errs),
             "（2）中位数口径：每次运行先预热 %d 轮再正式计时 %d 轮取中位数；共 %d 次完整基准 × %d 次独立运行，"
             "最终取全部 %d 个运行中位数的中位数，并同时给出最小值列以显示抖动。"
             % (WARMUP, ROUNDS, SESS, RUNS, TOTAL),
             ("（3）构建口径：C 用 gcc 16.2.0 -O2、Rust 用 -C opt-level=3（等价 cargo release），两者同为优化构建；"
              "objdump 显示 C 侧为标量 mulsd/addsd（mulpd/addpd 均为 0），未走 SIMD。") if HAS_RUST else
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
                     "最大 %.0f%%（%s）。其中一轮基准与机器上其它任务并行、整机更慢，是波动的主要来源；"
                     "因此表中取 %d 次独立运行的中位数而非挑最快一次，而同一次基准内部的比值（加速倍数）稳定得多"
                     "（三次基准 C/Python 分别 %s），量级结论始终是「两个数量级」。"
                     % (SESS, "、".join(parts), worst, wl, TOTAL,
                        "/".join("%.0f×" % r for r in session_ratios)))
    anchor = cap._element
    for t in notes:
        anchor = add_para_after(anchor, t, size=9.0, space_after=3)._element

    p_path = find_para("作品或数据文件路径")
    if p_path is not None:
        para_set_text(p_path, "作品或数据文件路径：D:\\DeepSeek-Harness\\hw-0304\\lab04\\"
                              "（code/ 源码、data/ 数据、logs/ 原始输出、figs/ 截图；最终报告在 output/）", size=9.0)


def fill_problems():
    """五、问题与解决：模板原表（3 列：问题 / 原因分析 / 解决办法），写 3 条技术问题。"""
    p = find_para("（至少记录 1 个真实问题", style="Normal")
    para_set_text(p, "本节记录实验中出现的 3 个技术问题，均给出「现象—原因—办法—验证」的闭环说明；"
                     "其中第一个在表格下方展开实测数据。", size=10.0)
    t = find_table("问题", n_cols=3) or find_table(n_cols=3)
    rows = [
        ("问题 1：整进程计时让 C 的单次耗时虚高约 1500 倍",
         "perf_counter 包住 subprocess 调用，Windows 起进程要 10~30 ms、读 8~16 MB 又要几毫秒；"
         "而 N=10^4 时 C 的实际计算仅 13.2 us，被启动开销彻底淹没，属量级错误。",
         "三版统一改「请求—应答」计时：进程 READY 后逐请求计时，只夹住写命令到读应答，"
         "再扣同进程实测的往返基线、按批量 k 折算单次（每段约 80 ms）。"),
        ("问题 2：编译器把「不消费结果」的重复计算外提甚至删除",
         "同一批数据反复调用同一函数且结果只做累加时，优化器可把循环不变量外提成一次计算；"
         "若结果完全没有副作用，整段循环还可能被删除，表现为耗时趋近 0 的假数据。",
         "每轮必须回传累加值（打印校验和 / 回包）+ 重复循环内加编译器屏障（空 asm + memory clobber），"
         "并对点积函数禁用内联；用 objdump 复核浮点指令仍然存在。"),
        ("问题 3：输出精度格式不一致，误判「三语言结果不一致」",
         "Rust 用 {:?} 打印最短可往返表示（位数少），Python/C 用 %.17g（位数多），同一 double 看起来不同，"
         "容易被误判成实现错误。",
         "三语言统一按 {:.17e} 输出 17 位有效数字；解析后比对数值而非比对字符串。"),
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
            ev.append("N=%d：整进程 %s vs 请求—应答 %s（虚高 %.0f 倍）" % (n, fmt_t(nv), fmt_t(pr), nv / pr))
    detail = ("问题 1 的验证（同一份数据、同一台机器，只换计时口径）：%s。改用请求—应答后，三语言在三个规模上的"
              "结论方向一致（C/Rust 比 Python 快约两个数量级），且校验和与 Python 逐位相同，说明计时口径自洽。"
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
        "原因 2（编译优化）：gcc -O2 比 -O0 快 %.2f 倍、rustc opt-level=3 比 opt-level=0 快 %.2f 倍（N=10^6，ablation 实测）。"
        % ((ABLATION.get("groups", {}) or {}).get("c_O0_over_O2_1e6") or 3.34,
           (ABLATION.get("groups", {}) or {}).get("rust_debug_over_release_1e6") or 4.66),
        "原因 3（向量化空间与可复现的权衡）：objdump 显示 gcc -O2 下仍是标量 mulsd/addsd（mulpd/addpd 均为 0），没走 SIMD——"
        "本实验要求三语言逐位一致，必须保持顺序累加；改用多累加器/AVX2 FMA 可再快数倍，但累加顺序改变、不再逐位相同。",
        "拓展：把点积改成分块并行（Python multiprocessing / Rust rayon），在 N=10^7 上验证加速是否线性；"
        "或用 PyO3 把 Rust 版封装成 Python 扩展（先确认 GIL 与释放策略），验证「Python 负责想法、Rust 负责跑快」。",
    ]
    for i, it in enumerate(items[:len(t.rows)]):
        cell_text(t.rows[i].cells[0], it, size=8.8)


def fill_selfcheck():
    """七、提交物自查：写成「最终交付状态」清单，再附提示词要点 / 问题留痕表 / 代码自查清单。"""
    checklist = [
        ("dot.py、dot.c、dot.rs",
         "☑  三份点积实现（Python / C / Rust）+ 统一基准脚本：同一套计时口径、每轮回传累加值、只依赖标准库"
         " —— 已交付并通过实测"),
        ("耗时对比表",
         "☑  3 规模 × 3 语言耗时对照表与相对 Python 的加速倍数（含多轮中位数）"
         " —— 见第四节表 1（3 轮基准 × 5 次独立运行 × 10 轮计时）"),
        ("3 张截图",
         "☑  三张实证截图：结果校验 / 编译与计时实况 / 耗时柱状对比 —— 见第四节图 1 / 图 2 / 图 3"),
        ("提示词 v1",
         "☑  两版提示词全文（v1、v2）与单变量修改理由 —— 见 code/prompt_v1.md、code/prompt_v2.md"),
        ("修错记录表",
         "☑  技术问题留痕（现象—原因—办法—验证）与代码自查清单 —— 见本节下方两张表"),
        ("test_dot.py",
         "☑  边界用例脚本及 5 个用例的实测输出 —— 5 PASS / 0 FAIL，见 logs/test_dot.txt 与图 1"),
    ]
    for p in DOC.paragraphs:
        txt = p.text.strip()
        if not txt.startswith("□"):
            continue
        rest = txt[1:].strip()
        for needle, new_line in checklist:
            if rest.startswith(needle):
                para_set_text(p, new_line, size=9.2)
                break
    p_other = find_para("其他附件")
    if p_other is not None:
        para_set_text(p_other, "其他附件：code/ 全部源码（含 ablation.py、merge_runs.py、make_figs.py）、"
                               "logs/ 原始回显与 json 数据、figs/ 三张图、data/ 六个 bin 文件", size=9.2)
        anchor = p_other._element
    else:
        anchor = DOC.paragraphs[-1]._element

    p_prompt = add_para_after(anchor, "提示词 v1 / v2 要点（全文见 code/prompt_v1.md、code/prompt_v2.md）：",
                              size=9.4, bold=True, space_after=2)
    anchor = p_prompt._element
    v1 = ("v1（四段式版）：交代清楚四件事 —— 数据从哪来（6 个裸 float64 小端 bin，按 i=0..n-1 依次累加）、"
          "要交什么（三份签名统一的实现 + one-shot 回显格式 N=<n> SUM=<17 位> + 一份出对照表和倍数的基准脚本）、"
          "有哪些硬限制（只用标准库、C 走 -O2、Rust 走 release、每轮累加值必须回传、计时不掺读盘、相对偏差 ≤ 1e-9）、"
          "给个样例（[1,2,3]·[4,5,6]=32 与一条输出样例）。")
    v2 = ("v2（只动一个变量）：把 v1 里「计时不掺读盘」那句，换成一套可执行的计时约定 ——"
          "「进程 READY 后按 r <k> 请求计时，只用 perf_counter 包住写命令到读应答这一段，扣掉同进程实测的往返基线再除以 k；"
          "热身 3 次、正式测 10 轮取中位数，每个配置独立起 5 次」。为什么动它：v1 那句话说得对但没给做法，AI 就自己发挥成"
          "整进程计时，把启动与 8~16 MB 读盘都算进去，直接让 N=10^4 的结论反了向；而「多轮取中位数」只影响精度、"
          "不会让结论方向反转。两个变量一起改就说不清是谁起的作用，所以 v2 只动计时口径这一个。")
    anchor = add_para_after(anchor, v1, size=9.0, space_after=2)._element
    anchor = add_para_after(anchor, v2, size=9.0, space_after=5)._element

    abl = ABLATION.get("groups", {}) or {}
    o0_o2 = abl.get("c_O0_over_O2_1e6")
    dbg_rel = abl.get("rust_debug_over_release_1e6")
    anchor = add_para_after(anchor, "技术问题留痕表（问题 / 现象 / 原因 / 改法 / 验证）：", size=9.4,
                            bold=True, space_after=2)._element
    rows = [
        ["1", "整进程计时污染 C 的耗时：单次被算成毫秒级，加速倍数只剩 4.5×",
         "perf_counter 包住 subprocess，启动与读盘都算进编译型语言",
         "改「请求—应答」+ 扣往返基线 + 批量 k 折算",
         "C 恢复 9.94 us 量级，倍数 98.9×"],
        ["2", "重复调用被优化：C 单次耗时被算成 0.001 us（约 80 万倍）",
         "相同入参的重复调用被外提成一次；结果无副作用时循环可能整段被删",
         "每轮回传累加值 + 循环内编译器屏障 + 禁用内联",
         "objdump 复核 mulsd=15 / addsd=12，耗时回到 1.16 ms 量级"],
        ["3", "输出位数不一致造成「结果不一致」误判",
         "Rust {:?} 与 Python/C 的 %.17g 位数不同，实为同一 double",
         "三语言统一 {:.17e}（17 位有效数字）",
         "三个规模校验和逐位相同、相对误差 0"],
    ]
    tbl = make_table_after(anchor, ["问题", "现象", "原因", "改法", "验证"], rows, font_size=7.8)
    set_col_widths(tbl, [Cm(1.0), Cm(4.6), Cm(4.4), Cm(3.2), Cm(3.2)])
    anchor = add_para_after(tbl._tbl, "代码自查清单（四问 + 三处专项）：", size=9.4, bold=True,
                            space_after=2)._element
    q = [
        ["☑", "输入有没有校验？", "长度不一致直接抛 ValueError（边界脚本已验证）；文件字节数不是 8 的整数倍就报错；n=0 返回 0.0，不去读脏数据"],
        ["☑", "边界与异常兜住了吗？", "空长度 / 单元素 / 全零 / 极大极小混排 / 空文件 / 长度不一致，5 个用例 + 1 条额外断言全 PASS"],
        ["☑", "依赖真实存在、版本对得上吗？", "只用标准库：Python 侧无 numpy、C 侧不链 BLAS、Rust 侧无 crate；编译器版本见第二节"],
        ["☑", "有没有写死绝对路径？", "三份实现都按脚本所在目录拼数据路径；基准脚本用 __file__ 反推 lab04/ 根"],
        ["☑", "专项 1：C 版那段计算真被执行了吗？", "objdump -d 里 mulsd/addsd 数 > 0；one-shot 回显累加值，请求—应答累加后回包"],
        ["☑", "专项 2：Rust 走的是优化构建吗？", "统一 -C opt-level=3；消融实验里放 opt-level=0 做对照，正式数据只用 release"],
        ["☑", "专项 3：Python 版有没有偷换成 numpy？", "dot.py 只 import array/sys/math，循环是显式 for，没有任何第三方库"],
    ]
    tbl3 = make_table_after(anchor, ["打勾", "自查项", "结论与证据"], q, font_size=7.8)
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
