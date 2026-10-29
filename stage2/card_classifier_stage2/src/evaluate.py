# -*- coding: utf-8 -*-
"""Evaluation utilities: metrics, confusion matrix, misclassifications, timing."""

from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import cv2
import numpy as np
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, precision_recall_fscore_support)

from .card_labels import LABELS, is_valid_label
from .image_utils import IMAGE_EXTS, read_image


def collect_items(images_dir) -> List[tuple]:
    """Return [(path, truth_label)] from a class-folder tree or flat prefixed files."""
    images_dir = Path(images_dir)
    if not images_dir.exists():
        raise FileNotFoundError(f"test image directory not found: {images_dir}")
    items = []
    subdirs = [p for p in images_dir.iterdir() if p.is_dir() and is_valid_label(p.name)]
    if subdirs:
        for d in sorted(subdirs):
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                    items.append((p, d.name.upper()))
    else:
        for p in sorted(images_dir.iterdir()):
            if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
                continue
            prefix = p.stem.split("_")[0].upper()
            if not is_valid_label(prefix):
                raise ValueError(f"cannot infer label from filename: {p.name}")
            items.append((p, prefix))
    if not items:
        raise RuntimeError(f"no images found in {images_dir}")
    return items


def _write_confusion_png(cm: np.ndarray, path: Path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(16, 14))
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    ax.set_title(title)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ticks = np.arange(len(LABELS))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(LABELS, rotation=90, fontsize=6)
    ax.set_yticklabels(LABELS, fontsize=6)
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _threshold_curve(rows, path_csv: Path, path_png: Path):
    scores = np.array([r["score"] for r in rows], dtype=float)
    correct = np.array([1 if r["best_label"] == r["truth"] else 0 for r in rows])
    if len(scores) == 0:
        return None
    lo, hi = float(scores.min()), float(scores.max())
    thresholds = np.linspace(lo, hi, 101)
    out = []
    for t in thresholds:
        accepted = scores >= t
        n = int(accepted.sum())
        cov = n / len(scores)
        acc = float(correct[accepted].mean()) if n else 0.0
        out.append({"threshold": round(float(t), 5), "coverage": round(cov, 5),
                    "accepted_accuracy": round(acc, 5), "accepted": n})
    with path_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        xs = [o["coverage"] for o in out]
        ys = [o["accepted_accuracy"] for o in out]
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(xs, ys, marker=".")
        ax.set_xlabel("coverage (accepted fraction)")
        ax.set_ylabel("accuracy on accepted")
        ax.set_title("Score threshold trade-off (not a calibrated probability)")
        ax.grid(True, ls=":")
        fig.tight_layout()
        path_png.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path_png, dpi=150)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover - plotting is best effort
        print(f"[WARN] threshold plot failed: {exc}")
    return out


def evaluate_folder(images_dir, classifier, output_dir="outputs", split_name="test",
                    save_previews=0):
    """Run a classifier over a folder and write a full evaluation report."""
    from .image_utils import make_preview

    images_dir = Path(images_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    items = collect_items(images_dir)
    print(f"[eval] {split_name}: {len(items)} images from {images_dir}")

    rows, times = [], []
    detect_ok = 0
    for i, (path, truth) in enumerate(items, start=1):
        t0 = time.perf_counter()
        result = classifier.predict(path)
        dt = (time.perf_counter() - t0) * 1000
        times.append(dt)
        detect_ok += int(result.get("detected", False))
        top5 = result.get("top5") or [[result["best_label"], result["score"]]]
        row = {
            "image": str(path),
            "truth": truth,
            "label": result["label"],
            "best_label": result["best_label"],
            "correct": result["best_label"] == truth,
            "score": float(result["score"]),
            "margin": float(result.get("margin") or 0.0),
            "detected": bool(result.get("detected", False)),
            "top1": top5[0][0] if len(top5) > 0 else "",
            "top2": top5[1][0] if len(top5) > 1 else "",
            "top3": top5[2][0] if len(top5) > 2 else "",
            "top4": top5[3][0] if len(top5) > 3 else "",
            "top5": top5[4][0] if len(top5) > 4 else "",
            "milliseconds": round(dt, 2),
        }
        rows.append(row)
        if save_previews and i <= save_previews:
            try:
                image = read_image(path)
                make_preview(image, result["label"], result["score"],
                             output_dir / f"preview_{i:03d}_{path.stem}.jpg",
                             quad=result.get("quad"))
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] preview failed for {path.name}: {exc}")
        if i % 50 == 0:
            print(f"[eval] {i}/{len(items)}")

    truth = [r["truth"] for r in rows]
    pred = [r["best_label"] for r in rows]
    acc = float(accuracy_score(truth, pred))
    # Rank / suit decomposition: a 10C -> 10S error is a suit error, while
    # 10C -> 9C is a rank error.  This makes the failure mode interpretable.
    rank_acc = sum(t[0:-1] == p[0:-1] for t, p in zip(truth, pred)) / len(rows)
    suit_acc = sum(t[-1] == p[-1] for t, p in zip(truth, pred)) / len(rows)
    report = classification_report(truth, pred, labels=LABELS, zero_division=0,
                                   output_dict=True)
    cm = confusion_matrix(truth, pred, labels=LABELS)
    macro = precision_recall_fscore_support(truth, pred, labels=LABELS,
                                            average="macro", zero_division=0)
    topk = {}
    for k in (1, 2, 3, 5):
        ok = sum(1 for r in rows if r["truth"] in [r[f"top{i}"] for i in range(1, k + 1)])
        topk[f"top{k}"] = ok / len(rows)
    times_arr = np.array(times)
    metrics = {
        "split": split_name,
        "classifier": getattr(classifier, "name", type(classifier).__name__),
        "num_images": len(rows),
        "accuracy_top1": acc,
        "rank_accuracy": rank_acc,
        "suit_accuracy": suit_acc,
        "topk": topk,
        "macro_precision": float(macro[0]),
        "macro_recall": float(macro[1]),
        "macro_f1": float(macro[2]),
        "detection_rate": detect_ok / len(rows),
        "latency_ms": {
            "mean": float(times_arr.mean()),
            "median": float(np.median(times_arr)),
            "p95": float(np.percentile(times_arr, 95)),
        },
        "per_class": {label: {
            "precision": report[label]["precision"],
            "recall": report[label]["recall"],
            "f1": report[label]["f1-score"],
            "support": report[label]["support"],
        } for label in LABELS},
        "confusion_matrix": cm.tolist(),
        "classes": LABELS,
    }

    # CSV predictions + misclassified list
    fieldnames = list(rows[0].keys())
    with (output_dir / f"predictions_{split_name}.csv").open(
            "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    misses = [r for r in rows if not r["correct"]]
    if misses:
        with (output_dir / f"misclassified_{split_name}.csv").open(
                "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(misses)

    # Confusion matrix CSV + PNG
    with (output_dir / f"confusion_matrix_{split_name}.csv").open(
            "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["truth\\pred"] + LABELS)
        for label, row in zip(LABELS, cm.tolist()):
            w.writerow([label] + row)
    _write_confusion_png(cm, output_dir / f"confusion_matrix_{split_name}.png",
                         f"{metrics['classifier']} / {split_name} (acc={acc:.4f})")

    curve = _threshold_curve(rows, output_dir / f"threshold_curve_{split_name}.csv",
                             output_dir / f"threshold_curve_{split_name}.png")
    if curve:
        metrics["threshold_curve_points"] = len(curve)

    (output_dir / f"metrics_{split_name}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Evaluation: {metrics['classifier']} / {split_name}", "",
        f"- images: {metrics['num_images']}",
        f"- top-1 accuracy: **{acc:.4f}**",
        f"- rank accuracy: {rank_acc:.4f}; suit accuracy: {suit_acc:.4f}",
        f"- top-3 accuracy: {topk['top3']:.4f}",
        f"- top-5 accuracy: {topk['top5']:.4f}",
        f"- macro precision / recall / F1: {macro[0]:.4f} / {macro[1]:.4f} / {macro[2]:.4f}",
        f"- card detection rate (on these inputs): {metrics['detection_rate']:.4f}",
        "  (processed datasets are already rectified; raw-photo auto-detection is reported in data/dataset_report.md)",
        f"- latency mean / p95: {metrics['latency_ms']['mean']:.1f} / "
        f"{metrics['latency_ms']['p95']:.1f} ms",
        f"- misclassified: {len(misses)}", "",
    ]
    (output_dir / f"metrics_{split_name}.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"[eval] acc={acc:.4f} macroF1={macro[2]:.4f} "
          f"latency={metrics['latency_ms']['mean']:.1f}ms")
    print(f"[eval] wrote metrics to {output_dir}")
    return metrics, rows


def evaluate_splits(splits_json, classifier, output_dir="outputs", which=None):
    """Evaluate a classifier on named splits from data/splits.json."""
    splits_json = Path(splits_json)
    data = json.loads(splits_json.read_text(encoding="utf-8"))
    root = splits_json.parent
    wanted = which or [("jackfurby_test", "jackfurby", "test"),
                       ("real52_test", "real52", "test")]
    results = {}
    for name, family, split in wanted:
        items = data.get(family, {}).get(split, [])
        if not items:
            continue
        # Build a temporary folder index: use the class-folder tree if available.
        paths = [root / item["path"] for item in items]
        images_dir = paths[0].parent.parent
        metrics, _ = evaluate_folder(images_dir, classifier, output_dir,
                                     split_name=name)
        results[name] = metrics
    return results
