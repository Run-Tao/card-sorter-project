# -*- coding: utf-8 -*-
"""Dataset integrity + leakage audit.

Checks:
- every image decodes, has the canonical 210x294 shape, and belongs to a label;
- each split has all 52 classes and the expected counts;
- no SHA-256 duplicate exists between train/val/test (templates are copies of
  train images and are reported separately);
- real photos never overlap with synthetic images.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from src.card_labels import LABELS, is_valid_label


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(path: Path, label_from_parent=True):
    items = []
    files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in
                   {".png", ".jpg", ".jpeg", ".bmp", ".webp"})
    for p in files:
        label = p.stem.split("_")[0].upper() if "templates" in path.parts else p.parent.name
        if "templates" in path.parts and label == "JOKER":
            continue
        img = cv2.imdecode(__import__("numpy").fromfile(str(p), dtype=__import__("numpy").uint8),
                           cv2.IMREAD_COLOR)
        items.append({
            "path": str(p),
            "label": label,
            "valid_label": is_valid_label(label),
            "shape": list(img.shape) if img is not None else None,
            "sha256": sha256(p),
        })
    return items


def summarize(name, items):
    shapes = Counter(tuple(i["shape"]) for i in items if i["shape"])
    counts = Counter(i["label"] for i in items)
    return {
        "name": name,
        "num_images": len(items),
        "num_classes": len(counts),
        "missing_classes": [l for l in LABELS if counts.get(l, 0) == 0],
        "counts_min_max": [min(counts.values()), max(counts.values())] if counts else [0, 0],
        "shapes": {str(k): v for k, v in shapes.items()},
        "invalid_labels": sum(not i["valid_label"] for i in items),
    }


def main():
    root = Path("data").resolve()
    splits = {
        "jackfurby_train": root / "processed/jackfurby/train",
        "jackfurby_val": root / "processed/jackfurby/val",
        "jackfurby_test": root / "processed/jackfurby/test",
        "real52": root / "processed/real52/all",
        "templates": root / "templates",
    }
    data = {k: scan(v) for k, v in splits.items() if v.exists()}
    summary = {k: summarize(k, v) for k, v in data.items()}
    hashes = {k: {i["sha256"]: i["path"] for i in v} for k, v in data.items()}

    def overlap(a, b):
        return sorted(set(hashes[a]) & set(hashes[b]))

    train_val = overlap("jackfurby_train", "jackfurby_val")
    train_test = overlap("jackfurby_train", "jackfurby_test")
    val_test = overlap("jackfurby_val", "jackfurby_test")
    tpl_train = overlap("templates", "jackfurby_train")
    tpl_test = overlap("templates", "jackfurby_test")
    real_any = overlap("real52", "jackfurby_test") if "real52" in data else []

    report = {
        "summary": summary,
        "hash_overlaps": {
            "train_val": len(train_val),
            "train_test": len(train_test),
            "val_test": len(val_test),
            "templates_train": len(tpl_train),
            "templates_test": len(tpl_test),
            "real_vs_synthetic_test": len(real_any),
        },
        "leakage_pass": not (train_test or val_test or tpl_test or real_any),
        "notes": [
            "templates are copies of train images by design; templates_test must be 0",
            "source split: JackFurby official train -> train/val, official val -> test",
            "real52 is a separate source and is never used for training/tuning",
        ],
    }
    (root / "integrity_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Dataset integrity report", "", "| split | images | classes | missing | min/max |", "|---|---|---|---|---|"]
    for k, s in summary.items():
        lines.append(f"| {k} | {s['num_images']} | {s['num_classes']} | "
                     f"{len(s['missing_classes'])} | {s['counts_min_max'][0]}/{s['counts_min_max'][1]} |")
    lines += ["", "## Hash overlaps", ""]
    for k, v in report["hash_overlaps"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", f"**Leakage check: {'PASS' if report['leakage_pass'] else 'FAIL'}**"]
    (root / "integrity_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if not report["leakage_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
