#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diag_docx.py —— 检查生成后的 docx 结构：正文元素顺序、标题是否带 pageBreakBefore、行是否允许跨页。"""
import sys

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

path = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\DeepSeek-Harness\hw-0304\lab04\第04讲-Scaled Dot-Product 计算与 Python、C、Rust 效率对比-实验报告.docx"
d = Document(path)
body = d.element.body
pi = ti = 0
for child in body.iterchildren():
    tag = child.tag.split("}")[1]
    if tag == "p":
        p = Paragraph(child, d)
        pb = child.find(qn("w:pPr"))
        pb_flag = ""
        if pb is not None and pb.find(qn("w:pageBreakBefore")) is not None:
            pb_flag = "  <== pageBreakBefore"
        has_img = " [IMG]" if child.findall(".//" + qn("w:drawing")) else ""
        txt = p.text.strip()
        if txt or has_img:
            print("P%-2d [%-9s]%-8s %s%s" % (pi, p.style.name, has_img, txt[:70], pb_flag))
        pi += 1
    elif tag == "tbl":
        t = Table(child, d)
        cant = 0
        for row in t.rows:
            trPr = row._tr.find(qn("w:trPr"))
            if trPr is not None and trPr.find(qn("w:cantSplit")) is not None:
                cant += 1
        first = ""
        for c in t.rows[0].cells:
            if c.text.strip():
                first = c.text.strip()[:30]
                break
        print("T%-2d rows=%-3d cols=%-2d cantSplit=%-3d first=%r" % (ti, len(t.rows), len(t.columns), cant, first))
        ti += 1
print("\n--- 页脚字段 ---")
for sec in d.sections:
    for p in sec.footer.paragraphs:
        if p.text.strip():
            print(repr(p.text))
