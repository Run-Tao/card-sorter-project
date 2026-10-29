# -*- coding: utf-8 -*-
"""Summarize error patterns from the evaluation CSVs."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.card_labels import RANKS, SUITS


def read_rows(path):
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def split_rank_suit(label):
    return label[:-1], label[-1]


def summarize(rows):
    n = len(rows)
    rank_ok = sum(split_rank_suit(r["truth"])[0] == split_rank_suit(r["best_label"])[0] for r in rows)
    suit_ok = sum(split_rank_suit(r["truth"])[1] == split_rank_suit(r["best_label"])[1] for r in rows)
    confusions = Counter((r["truth"], r["best_label"]) for r in rows
                         if r["truth"] != r["best_label"])
    per_suit = defaultdict(lambda: [0, 0])
    per_rank = defaultdict(lambda: [0, 0])
    for r in rows:
        t_rank, t_suit = split_rank_suit(r["truth"])
        ok = int(r["truth"] == r["best_label"])
        per_suit[t_suit][0] += ok
        per_suit[t_suit][1] += 1
        per_rank[t_rank][0] += ok
        per_rank[t_rank][1] += 1
    return {
        "n": n,
        "accuracy": sum(r["truth"] == r["best_label"] for r in rows) / max(n, 1),
        "rank_accuracy": rank_ok / max(n, 1),
        "suit_accuracy": suit_ok / max(n, 1),
        "top_confusions": confusions.most_common(15),
        "per_suit": {s: {"acc": v[0] / max(v[1], 1), "n": v[1]} for s, v in per_suit.items()},
        "per_rank": {r: {"acc": v[0] / max(v[1], 1), "n": v[1]} for r, v in per_rank.items()},
    }


def main():
    root = Path(".").resolve()
    out = {}
    for model in ("template", "hog_svm", "cnn"):
        for split in ("jackfurby_test", "real52_test"):
            rows = read_rows(root / "outputs/eval" / model / f"predictions_{split}.csv")
            if rows:
                out[f"{model}/{split}"] = summarize(rows)

    # Real detection failure subset, using splits.json metadata.
    splits = json.loads((root / "data/splits.json").read_text(encoding="utf-8"))
    fallback_names = {Path(x["path"]).stem for x in splits["real52"]["test"]
                      if not x.get("detected", True)}
    for model in ("template", "hog_svm", "cnn"):
        rows = read_rows(root / "outputs/eval" / model / "predictions_real52_test.csv")
        if rows:
            sub = [r for r in rows if Path(r["image"]).stem in fallback_names]
            out[f"{model}/real52_detection_fallback"] = summarize(sub)

    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs/analysis.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Error analysis", ""]
    for key, s in out.items():
        lines += [f"## {key}", "",
                  f"- n={s['n']}, top-1={s['accuracy']:.4f}, rank={s['rank_accuracy']:.4f}, "
                  f"suit={s['suit_accuracy']:.4f}",
                  f"- top confusions: " + ", ".join(f"{a}->{b} ({c})" for (a, b), c in s["top_confusions"][:8]),
                  ""]
    (root / "outputs/analysis.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
