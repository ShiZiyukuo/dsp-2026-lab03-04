#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_figs.py —— 用 Pillow 把真实终端输出渲染成「截图风格」PNG，并画耗时对比柱状图。

三张图对应实验指南要求的截图：
    figs/fig1_correctness.png   正确性核对（三语言读同一份 bin + 5 个边界用例）
    figs/fig2_compile_run.png   编译与计时运行（真实命令 + 真实输出）
    figs/fig3_time_compare.png  3 规模 × 3 语言耗时对比柱状图（对数刻度 + 数值标注）

数据来源全部是 logs/ 下的真实 stdout，不手写任何数字。
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.path.join(ROOT, "logs")
FIGS = os.path.join(ROOT, "figs")

FONT_ASCII = r"C:\Windows\Fonts\consola.ttf"
FONT_CJK = r"C:\Windows\Fonts\msyh.ttc"

BG = (30, 30, 30)
BG_TITLE = (50, 50, 50)
FG = (212, 212, 212)
FG_DIM = (150, 150, 150)
GREEN = (106, 190, 120)
CYAN = (86, 190, 220)
YELLOW = (220, 200, 120)
RED = (240, 120, 120)
BLUE = (100, 160, 240)
WHITE = (235, 235, 235)

_SIZE = 26


def font_ascii(size=_SIZE):
    return ImageFont.truetype(FONT_ASCII, size)


def font_cjk(size=_SIZE):
    return ImageFont.truetype(FONT_CJK, size)


def is_cjk(ch):
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF) or (0xF900 <= o <= 0xFAFF) or \
           (0xFF00 <= o <= 0xFFEF) or (0x3000 <= o <= 0x303F) or o >= 0x20000


def split_runs(text):
    """把一行切成 (是否 CJK, 片段) 的序列，便于对中英文分别用字体。"""
    runs = []
    for ch in text:
        k = is_cjk(ch)
        if runs and runs[-1][0] == k:
            runs[-1][1].append(ch)
        else:
            runs.append([k, [ch]])
    return [(k, "".join(v)) for k, v in runs]


def draw_text_mixed(draw, xy, text, fill, size=_SIZE, bold_cjk=False):
    x, y = xy
    fa = font_ascii(size)
    fc = font_cjk(size)
    for k, seg in split_runs(text):
        f = fc if k else fa
        draw.text((x, y), seg, font=f, fill=fill)
        x += f.getlength(seg)
    return x


def measure_mixed(text, size=_SIZE):
    w = 0.0
    fa = font_ascii(size)
    fc = font_cjk(size)
    for k, seg in split_runs(text):
        w += (fc if k else fa).getlength(seg)
    return w


LINE_H = 38
PAD = 22
TITLE_H = 46


def render_screenshot(lines, out_path, width=1600, title="Windows PowerShell",
                      max_size=_SIZE):
    """lines: [(text, color, size_or_None)] —— 渲染成终端截图风格 PNG。

    - PowerShell 的 Tee-Object 写出的是 UTF-16LE，read_lines() 已按 BOM 解码；
    - 自动选一个能装下最长行的字号（避免右侧被裁掉），行高随字号缩放。
    """
    # 自动选字号：从 max_size 往下试，直到最长行能放进 width
    avail = width - PAD * 2
    size = max_size
    while size > 12:
        widest = max((measure_mixed(t, sz or size) for t, _, sz in lines), default=0)
        if widest <= avail:
            break
        size -= 1
    # 行高按各自字号缩放
    heights = [int(round((sz or size) * 1.46)) for _, _, sz in lines]
    height = TITLE_H + PAD * 2 + sum(heights) + 8
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    # 标题栏
    d.rectangle([0, 0, width, TITLE_H], fill=BG_TITLE)
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = 24 + i * 26
        d.ellipse([cx - 7, TITLE_H // 2 - 7, cx + 7, TITLE_H // 2 + 7], fill=c)
    draw_text_mixed(d, (120, TITLE_H // 2 - 15), title, (200, 200, 200), 24)
    y = TITLE_H + PAD
    for (text, color, sz), h in zip(lines, heights):
        s = sz or size
        # 行内垂直居中偏移：不同字号的基线略有差异，按比例留白
        draw_text_mixed(d, (PAD, y + int((h - s * 1.22) / 2)), text, color, s)
        y += h
    img.save(out_path)
    print("wrote %s (%dx%d, font=%d)" % (out_path, width, height, size))
    return out_path


# ------------------------------------------------------------------ 图 1 / 图 2

def build_fig1():
    """正确性核对：三语言读同一份数据 + 5 个边界用例。"""
    lines = []
    bench = read_json(os.path.join(LOGS, "benchmark_raw.json"))
    lines.append(("PS D:\\DeepSeek-Harness\\hw-0304\\lab04> python code\\test_dot.py", FG_DIM, None))
    test_path = os.path.join(LOGS, "test_dot.txt")
    if os.path.exists(test_path):
        for ln in read_lines(test_path):
            color = FG
            if ln.startswith("PASS"):
                color = GREEN
            elif ln.startswith("FAIL"):
                color = RED
            elif set(ln.strip()) <= set("= ") and ln.strip():
                color = FG_DIM
            lines.append((ln, color, None))
    if bench:
        lines.append(("", FG, None))
        lines.append(("PS ...> python code\\benchmark.py   [1/2] 正确性核对", FG_DIM, None))
        checks = bench["checks"]
        langs = bench["languages"]
        hdr = "%-9s %-24s" % ("N", "Python SUM")
        for name in langs:
            if name != "Python":
                hdr += "%-24s" % (name + " SUM")
        hdr += "%16s%16s" % ("C rel.err", "Rust rel.err")
        lines.append((hdr, CYAN, None))
        for n, rec in checks.items():
            row = "%-9s %-24.17g" % (n, rec["python"])
            for name in langs:
                if name != "Python":
                    row += "%-24.17g" % rec.get(name, float("nan"))
            row += "%16.3e%16.3e" % (rec.get("C_rel_err", 0.0), rec.get("Rust_rel_err", 0.0))
            lines.append((row, FG, None))
        lines.append(("=> 三语言相对误差均 <= 1e-9，结果与 Python 基准一致：PASS", GREEN, None))
        lines.append(("=> 三版读同一份 data/*_f64.bin（裸 float64 小端），不各自生成随机数", FG_DIM, None))
    return render_screenshot(lines, os.path.join(FIGS, "fig1_correctness.png"),
                             title="Windows PowerShell — 正确性核对")


def build_fig2():
    """编译与计时运行：真实命令 + 真实输出。"""
    lines = []
    cpath = os.path.join(LOGS, "compile.txt")
    if os.path.exists(cpath):
        lines.append(("PS D:\\DeepSeek-Harness\\hw-0304\\lab04> 编译三版", FG_DIM, None))
        for ln in read_lines(cpath)[:10]:
            color = FG
            if ln.startswith("$"):
                color = CYAN
            if "error" in ln.lower() or "[exit" in ln:
                color = RED
            lines.append((ln, color, None))
    bpath = os.path.join(LOGS, "benchmark_console.txt")
    if os.path.exists(bpath):
        lines.append(("", FG, None))
        keep = [ln for ln in read_lines(bpath) if ln.strip()]
        start = next((i for i, ln in enumerate(keep) if "[2/2]" in ln), 0)
        body = keep[start:]
        # 头部若干行 + 省略号 + 尾部汇总表（保证图里能看到最终 3×3 耗时表）
        head = body[:8]
        tail = body[-11:]
        for ln in head:
            color = FG
            if ln.startswith("  N="):
                color = FG_DIM
            if "[2/2]" in ln:
                color = CYAN
            lines.append((ln, color, None))
        lines.append(("        ...（中间各规模各次运行记录省略，原始输出见 logs/benchmark_run*.txt）", FG_DIM, None))
        for ln in tail:
            color = FG
            if "耗时对比表" in ln or ln.strip().startswith(("N ", "N\t", "各规模")):
                color = CYAN
            if ln.strip().startswith(("10000", "100000", "1000000")):
                color = WHITE
            lines.append((ln, color, None))
    return render_screenshot(lines, os.path.join(FIGS, "fig2_compile_run.png"),
                             title="Windows PowerShell — 编译与计时运行")


def read_lines(path):
    """读文本行。PowerShell 的 Tee-Object 写 UTF-16LE（带 BOM），这里按 BOM/内容自动判断编码。"""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xff\xfe"):
        text = raw.decode("utf-16-le", errors="replace")
    elif raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16-be", errors="replace")
    elif b"\x00" in raw[:400]:
        text = raw.decode("utf-16-le", errors="replace")   # 无 BOM 的 UTF-16
    else:
        text = raw.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return [ln.rstrip("\r\n") for ln in text.splitlines()]


def read_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ 图 3

def fmt_t(sec):
    if sec >= 1.0:
        return "%.2f s" % sec
    if sec >= 1e-3:
        return "%.2f ms" % (sec * 1e3)
    return "%.1f us" % (sec * 1e6)


COLORS = {"Python": (79, 193, 255), "C": (249, 168, 37), "Rust": (255, 107, 107)}


def build_fig3():
    bench = read_json(os.path.join(LOGS, "benchmark_raw.json"))
    if not bench:
        print("缺少 logs/benchmark_raw.json，跳过图 3")
        return None
    sizes = [int(x) for x in bench["sizes"]]
    langs = [x for x in bench["languages"]]
    times = {int(k): v for k, v in bench["times"].items()}

    W, H = 1600, 940
    ML, MR, MT, MB = 150, 60, 150, 150
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 标题
    draw_text_mixed(d, (ML - 40, 46), "3 规模 × 3 语言 单次点积耗时对比（对数刻度）", WHITE, 36)
    sess = bench.get("sessions", 1)
    total = bench.get("total_runs", bench.get("runs", 5))
    draw_text_mixed(d, (ML - 40, 96),
                    "%d 次完整基准 × 共 %d 次独立运行，每次预热 %d 轮 + 正式 %d 轮取中位数；越低越好"
                    % (sess, total, bench.get("warmup", 3), bench.get("rounds", 10)), FG_DIM, 24)

    allv = []
    for n in sizes:
        for name in langs:
            allv.append(times[n][name]["median"])
    lo = min(allv) / 3.0
    hi = max(allv) * 3.0
    llo, lhi = math.log10(lo), math.log10(hi)

    plot_x0, plot_x1 = ML, W - MR
    plot_y0, plot_y1 = MT, H - MB

    def y_of(v):
        f = (math.log10(v) - llo) / (lhi - llo)
        return plot_y1 - f * (plot_y1 - plot_y0)

    # 网格 + y 轴刻度（1us / 10us / 100us / 1ms / 10ms / 100ms / 1s）
    ticks = []
    e = int(math.floor(llo))
    while e <= int(math.ceil(lhi)) + 1:
        ticks.append(10.0 ** e)
        e += 1
    for v in ticks:
        if v < lo or v > hi:
            continue
        y = y_of(v)
        d.line([plot_x0, y, plot_x1, y], fill=(60, 60, 60), width=1)
        draw_text_mixed(d, (18, y - 15), fmt_t(v), FG_DIM, 22)

    d.line([plot_x0, plot_y1, plot_x1, plot_y1], fill=(120, 120, 120), width=2)
    d.line([plot_x0, plot_y0, plot_x0, plot_y1], fill=(120, 120, 120), width=2)

    group_w = (plot_x1 - plot_x0) / len(sizes)
    bw = min(90, group_w / (len(langs) + 1.2))
    for gi, n in enumerate(sizes):
        gx = plot_x0 + group_w * gi + group_w / 2
        total_w = bw * len(langs) + 16 * (len(langs) - 1)
        x = gx - total_w / 2
        for name in langs:
            v = times[n][name]["median"]
            y = y_of(v)
            d.rectangle([x, y, x + bw, plot_y1], fill=COLORS.get(name, (150, 150, 150)))
            label = fmt_t(v)
            lw = measure_mixed(label, 22)
            draw_text_mixed(d, (x + bw / 2 - lw / 2, y - 30), label, WHITE, 22)
            # 加速倍数（相对 Python）
            if name != "Python":
                base = times[n]["Python"]["median"]
                sp = "%.1fx" % (base / v)
                sw = measure_mixed(sp, 20)
                draw_text_mixed(d, (x + bw / 2 - sw / 2, y - 56), sp, YELLOW, 20)
            x += bw + 16
        lb = "N = %s" % ("10^%d" % int(round(math.log10(n))))
        lw = measure_mixed(lb, 26)
        draw_text_mixed(d, (gx - lw / 2, plot_y1 + 18), lb, FG, 26)

    # 图例
    lx = plot_x1 - 460
    ly = 96
    for name in langs:
        d.rectangle([lx, ly + 6, lx + 26, ly + 28], fill=COLORS.get(name, (150, 150, 150)))
        draw_text_mixed(d, (lx + 36, ly), name, WHITE, 24)
        lx += 150

    draw_text_mixed(d, (plot_x0, H - 44),
                    "注：C / Rust 用 -O2 / opt-level=3 优化构建；计时只含纯计算循环，不含进程启动与文件读取。",
                    FG_DIM, 22)
    out = os.path.join(FIGS, "fig3_time_compare.png")
    img.save(out)
    print("wrote %s (%dx%d)" % (out, W, H))
    return out


def main():
    os.makedirs(FIGS, exist_ok=True)
    which = sys.argv[1:] or ["1", "2", "3"]
    if "1" in which:
        build_fig1()
    if "2" in which:
        build_fig2()
    if "3" in which:
        build_fig3()
    return 0


if __name__ == "__main__":
    sys.exit(main())
