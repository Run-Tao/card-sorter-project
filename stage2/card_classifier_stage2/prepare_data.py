# -*- coding: utf-8 -*-
"""Prepare reproducible datasets from the downloaded raw data.

Outputs
-------
data/processed/jackfurby/{train,val,test}/<label>/*.png
    Rectified single-card images from the synthetic JackFurby dataset.
    train/val come from the official train split (disjoint images);
    test comes from the official val split (never used for training).
data/processed/real52/all/<label>/*.png
    Rectified real photographs from drFarid/French-Playing-Cards.
    Used ONLY as a cross-source test set; never used for training/tuning.
data/templates/<label>.png
    One rectified card per class from the JackFurby train split, used by the
    template-matching baseline.
data/splits.json
    Machine-readable split definition (paths + labels).
data/dataset_report.json / dataset_report.md
    Counts, class balance, detection rate, licenses and limitations.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

from src.card_labels import LABELS, is_valid_label
from src.image_utils import (CANONICAL_SIZE, read_image, rectify_card,
                             rectify_card_from_points, save_image)

FRENCH_SUIT = {"coeur": "H", "carreau": "D", "pique": "S", "trefle": "C"}
FRENCH_RANK = {"valet": "J", "dame": "Q", "roi": "K", "as": "A"}


def french_folder_to_label(folder: str) -> str:
    parts = folder.strip().lower().split()
    if len(parts) != 2 or parts[0] not in FRENCH_SUIT:
        raise ValueError(f"cannot parse French card folder: {folder!r}")
    suit = FRENCH_SUIT[parts[0]]
    word = parts[1]
    if word.isdigit():
        n = int(word)
        rank = "A" if n == 1 else str(n)
    else:
        rank = FRENCH_RANK.get(word, "")
    label = rank + suit
    if not is_valid_label(label):
        raise ValueError(f"mapped invalid label from folder {folder!r}: {label!r}")
    return label


def clean_dir(path: Path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def jackfurby(manifest: dict, out_root: Path, per_class_train: int,
              per_class_val: int, per_class_test: int, overwrite: bool):
    records = manifest["jackfurby"]["images"]
    by_split = defaultdict(lambda: defaultdict(list))
    for rec in records:
        by_split[rec["split"]][rec["class_label"]].append(rec)

    processed = out_root / "processed" / "jackfurby"
    if overwrite:
        clean_dir(processed)
    splits = {"train": [], "val": [], "test": []}
    detection = {"ok": 0, "fallback": 0}
    for split in ("train", "val", "test"):
        src_split = "train" if split in ("train", "val") else "val"
        for label in LABELS:
            items = by_split[src_split].get(label, [])
            need = {"train": per_class_train, "val": per_class_val,
                    "test": per_class_test}[split]
            if split == "train":
                chosen = items[:per_class_train]
            elif split == "val":
                # IMPORTANT: val must be disjoint from train even though both
                # come from the official train split.
                chosen = items[per_class_train:per_class_train + per_class_val]
            else:
                chosen = items[:per_class_test]
            if len(chosen) < need:
                raise RuntimeError(
                    f"JackFurby {split}/{label}: need {need}, have {len(chosen)}")
            label_dir = processed / split / label
            label_dir.mkdir(parents=True, exist_ok=True)
            for i, rec in enumerate(chosen):
                raw = out_root / rec["local_path"]
                image = read_image(raw)
                pts = rec["card_points"][0][0]  # 4 points, TL,TR,BL,BR per dataset docs
                card = rectify_card_from_points(image, pts, size=CANONICAL_SIZE)
                dst = label_dir / f"{Path(rec['img_path']).stem}.png"
                save_image(dst, card)
                detection["ok"] += 1
                splits[split].append({"path": str(dst.relative_to(out_root)),
                                      "label": label,
                                      "source": "JackFurby/playing-cards"})
    return splits, detection


def real52(manifest: dict, out_root: Path, overwrite: bool):
    records = manifest.get("drfarid", {}).get("images", [])
    processed = out_root / "processed" / "real52"
    if overwrite:
        clean_dir(processed)
    splits = {"test": []}
    detection = {"ok": 0, "fallback": 0}
    per_class = Counter()
    for rec in records:
        label = french_folder_to_label(rec["folder"])
        raw = out_root / rec["local_path"]
        image = read_image(raw)
        card, info = rectify_card(image, size=CANONICAL_SIZE)
        detection["ok" if info["detected"] else "fallback"] += 1
        label_dir = processed / "all" / label
        label_dir.mkdir(parents=True, exist_ok=True)
        dst = label_dir / f"{Path(rec['local_path']).stem}.png"
        save_image(dst, card)
        per_class[label] += 1
        splits["test"].append({
            "path": str(dst.relative_to(out_root)),
            "label": label,
            "source": "drFarid/French-Playing-Cards",
            "detected": bool(info["detected"]),
        })
    return splits, detection, per_class


def make_templates(splits: dict, out_root: Path, overwrite: bool):
    tpl_dir = out_root / "templates"
    if overwrite:
        clean_dir(tpl_dir)
    by_label = defaultdict(list)
    for item in splits["train"]:
        by_label[item["label"]].append(item["path"])
    missing = [label for label in LABELS if not by_label.get(label)]
    if missing:
        raise RuntimeError(f"cannot build templates, missing classes: {missing}")
    mapping = {}
    for label in LABELS:
        src = out_root / by_label[label][0]
        dst = tpl_dir / f"{label}.png"
        save_image(dst, read_image(src))
        mapping[label] = str(dst.relative_to(out_root))
    return mapping


def check_split(split_name, items):
    counts = Counter(i["label"] for i in items)
    missing = [label for label in LABELS if counts.get(label, 0) == 0]
    unknown = [i for i in items if not is_valid_label(i["label"])]
    return {
        "name": split_name,
        "num_images": len(items),
        "num_classes": len(counts),
        "missing_classes": missing,
        "invalid_labels": len(unknown),
        "per_class_min": min(counts.values()) if counts else 0,
        "per_class_max": max(counts.values()) if counts else 0,
        "counts": dict(sorted(counts.items())),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data", help="data root")
    ap.add_argument("--manifest", default="data/download_manifest.json")
    ap.add_argument("--train-per-class", type=int, default=15)
    ap.add_argument("--val-per-class", type=int, default=5)
    ap.add_argument("--test-per-class", type=int, default=5)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    data = Path(args.data).resolve()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if not manifest.get("jackfurby", {}).get("images"):
        raise RuntimeError("manifest has no JackFurby images; run tools/download_datasets.py first")

    jf_splits, jf_det = jackfurby(manifest, data, args.train_per_class,
                                  args.val_per_class, args.test_per_class,
                                  args.overwrite)
    templates = make_templates(jf_splits, data, args.overwrite)

    real_splits, real_det, real_counts = {"test": []}, {"ok": 0, "fallback": 0}, Counter()
    if manifest.get("drfarid", {}).get("images"):
        real_splits, real_det, real_counts = real52(manifest, data, args.overwrite)

    splits = {
        "jackfurby": jf_splits,
        "real52": real_splits,
        "templates": templates,
        "labels": LABELS,
        "notes": {
            "jackfurby": "synthetic (machine-generated) single-card scenes; "
                         "train/val from official train split, test from official val split",
            "real52": "real photographs; each class folder appears to repeat photos "
                      "of one physical card, so this is a robustness/cross-source test, "
                      "not an unseen-physical-card benchmark",
        },
    }
    (data / "splits.json").write_text(json.dumps(splits, ensure_ascii=False, indent=2),
                                      encoding="utf-8")

    report = {
        "data_root": str(data),
        "licenses": {
            "JackFurby/playing-cards": "MIT",
            "drFarid/French-Playing-Cards": "MIT",
        },
        "splits": {
            name: check_split(name, items) for name, items in {
                "jackfurby_train": jf_splits["train"],
                "jackfurby_val": jf_splits["val"],
                "jackfurby_test": jf_splits["test"],
                "real52_test": real_splits["test"],
            }.items()
        },
        "detection": {
            "jackfurby_rectified_by_metadata": jf_det,
            "real52_auto_detect": real_det,
        },
        "real52_classes_present": len(real_counts),
        "limitations": [
            "JackFurby images are synthetic (one openclipart deck rendered on random backgrounds).",
            "drFarid real photos are per-class repeats of presumably one physical card each; "
            "splitting within a class would leak card identity, so the whole set is used only as a test set.",
            "No public dataset with multiple physical decks and card identity was downloaded; "
            "cross-brand / unseen-card generalisation remains unverified.",
        ],
    }
    (data / "dataset_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Dataset report", "",
             "## Splits", "",
             "| split | images | classes | per-class min/max | missing |",
             "|---|---|---|---|---|"]
    for name, info in report["splits"].items():
        lines.append(f"| {name} | {info['num_images']} | {info['num_classes']} | "
                     f"{info['per_class_min']}/{info['per_class_max']} | "
                     f"{len(info['missing_classes'])} |")
    lines += ["", "## Card detection on real photos", "",
              f"- auto-detected quad: {real_det['ok']}",
              f"- fallback full-image resize: {real_det['fallback']}",
              "", "## Known limitations", ""]
    lines += [f"- {x}" for x in report["limitations"]]
    (data / "dataset_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report["splits"], ensure_ascii=False, indent=2))
    print("real52 detection:", real_det)
    print("wrote:", data / "splits.json")
    print("wrote:", data / "dataset_report.md")


if __name__ == "__main__":
    main()
