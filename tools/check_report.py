# -*- coding: utf-8 -*-
import os
import re

md = r"report\无标记扑克牌自动分拣机_工程实施方案.md"
lines = open(md, encoding="utf-8").read().splitlines()

# table check
issues = []
i = 0
tidx = 0
while i < len(lines):
    if lines[i].startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
        tidx += 1
        header = [c for c in lines[i].strip().strip("|").split("|")]
        ncol = len(header)
        j = i + 2
        while j < len(lines) and lines[j].startswith("|"):
            row = [c for c in lines[j].strip().strip("|").split("|")]
            if len(row) != ncol:
                issues.append((j + 1, ncol, len(row), lines[j][:90]))
            j += 1
        i = j
    else:
        i += 1

print("tables:", tidx, "column mismatches:", len(issues))
for x in issues[:20]:
    print("  line", x[0], "header", x[1], "row", x[2], x[3])

# image check
imgs = re.findall(r"!\[[^\]]*\]\(([^)]+?)(?:\{[^}]*\})?\)", "\n".join(lines))
print("images:", imgs)
for p in imgs:
    full = os.path.join("report", p)
    print("  ", p, "exists", os.path.exists(full))

# heading count
h1 = [l for l in lines if l.startswith("# ")]
h2 = [l for l in lines if l.startswith("## ")]
print("H1", len(h1), "H2", len(h2))
print("chars", sum(len(l) for l in lines))
