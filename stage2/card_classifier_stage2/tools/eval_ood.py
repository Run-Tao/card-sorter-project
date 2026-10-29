# -*- coding: utf-8 -*-
"""Evaluate the template-similarity OOD gate on the available test splits."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classifier import TemplateCardClassifier
from src.evaluate import collect_items

THRESHOLD = 0.55


def stats(scores):
    arr = np.asarray(scores, dtype=float)
    return {
        "n": int(arr.size),
        "min": round(float(arr.min()), 3),
        "median": round(float(np.median(arr)), 3),
        "p90": round(float(np.percentile(arr, 90)), 3),
        "max": round(float(arr.max()), 3),
        "ood_rate": round(float((arr < THRESHOLD).mean()), 3),
    }


def main():
    clf = TemplateCardClassifier(ROOT / "data" / "templates")
    out = {"threshold": THRESHOLD, "splits": {}}
    for name, folder in (
        ("jackfurby_test", ROOT / "data/processed/jackfurby/test"),
        ("real52_test", ROOT / "data/processed/real52/all"),
    ):
        items = collect_items(folder)
        scores = [clf.predict(path)["score"] for path, _ in items]
        out["splits"][name] = stats(scores)
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "ood_eval.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# OOD gate evaluation", "",
             f"Template similarity threshold: {THRESHOLD}", "",
             "| split | n | min | median | p90 | max | OOD rate |",
             "|---|---|---|---|---|---|---|"]
    for name, s in out["splits"].items():
        lines.append(f"| {name} | {s['n']} | {s['min']} | {s['median']} | "
                     f"{s['p90']} | {s['max']} | {s['ood_rate']:.1%} |")
    lines += ["", "Synthetic = same design as training; real = another deck design.",
              "A high synthetic OOD rate would mean false rejection; a high real OOD rate",
              "is expected and is the reason unknown designs are sent to review/enrollment."]
    (ROOT / "outputs" / "ood_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
