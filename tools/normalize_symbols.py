# -*- coding: utf-8 -*-
"""把 PDF 字体不支持的符号替换为 ASCII/中文等价，避免 PDF 缺字。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEC = os.path.join(ROOT, "report", "sections")

# 先长后短，避免部分替换
STAR_MAP = [
    ("★★★★★", "★★★★★（很高）"),
    ("★★★☆", "★★★☆（中高）"),
    ("★★★★", "★★★★（高）"),
    ("★★☆", "★★☆（中低）"),
]
CHAR_MAP = {
    "▶": "->", "◀": "<-",
    "①": "(1)", "②": "(2)", "③": "(3)", "④": "(4)",
    "⑤": "(5)", "⑥": "(6)", "⑦": "(7)", "⑧": "(8)",
}
TEXT_MAP = {
    "评分说明：★越多越好；": "评分说明：",
    "c ∉ C": "c 不属于 C",
    "类别 ∉C": "类别 不属于 C",
    "∉C": "不属于 C",
}

changed = []
for fn in sorted(os.listdir(SEC)):
    if not fn.endswith(".md"):
        continue
    p = os.path.join(SEC, fn)
    s = open(p, encoding="utf-8").read()
    old = s
    for a, b in STAR_MAP:
        s = s.replace(a, b)
    for a, b in CHAR_MAP.items():
        s = s.replace(a, b)
    for a, b in TEXT_MAP.items():
        s = s.replace(a, b)
    if s != old:
        open(p, "w", encoding="utf-8", newline="\n").write(s)
        changed.append(fn)
print("changed:", changed)
