# -*- coding: utf-8 -*-
"""Compare template / HOG+SVM / CNN on the same held-out splits.

This script only evaluates existing artifacts; run prepare_data.py, train.py and
(optionally) evaluate_folder.py first.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.classifier import create_classifier
from src.evaluate import evaluate_folder


def main():
    root = Path(".").resolve()
    splits = json.loads((root / "data" / "splits.json").read_text(encoding="utf-8"))
    models = []
    if (root / "data" / "templates").exists():
        models.append(("template", create_classifier(
            "template", template_dir=root / "data" / "templates", threshold=None)))
    if (root / "models" / "hog_svm.joblib").exists():
        models.append(("hog_svm", create_classifier(
            "hog", model_path=root / "models" / "hog_svm.joblib", threshold=None)))
    if (root / "models" / "cnn.pt").exists():
        models.append(("cnn", create_classifier(
            "cnn", model_path=root / "models" / "cnn.pt", threshold=None)))
    if not models:
        raise RuntimeError("no models found; run prepare_data.py and train.py first")

    targets = [("jackfurby_test", root / "data/processed/jackfurby/test"),
               ("real52_test", root / "data/processed/real52/all")]
    rows = []
    all_metrics = {}
    for name, classifier in models:
        all_metrics[name] = {}
        for split_name, images_dir in targets:
            if not images_dir.exists():
                continue
            out = root / "outputs" / "eval" / name
            metrics, _ = evaluate_folder(images_dir, classifier, out, split_name)
            all_metrics[name][split_name] = metrics
            rows.append({
                "model": name,
                "split": split_name,
                "accuracy": metrics["accuracy_top1"],
                "macro_f1": metrics["macro_f1"],
                "top5": metrics["topk"]["top5"],
                "latency_ms": metrics["latency_ms"]["mean"],
                "detection_rate": metrics["detection_rate"],
                "n": metrics["num_images"],
            })
    out_dir = root / "outputs" / "comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(
        json.dumps({"rows": rows, "metrics": all_metrics}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    lines = ["# Model comparison (same held-out splits)", "",
             "| model | split | n | top-1 | macro F1 | top-5 | mean latency (ms) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['model']} | {r['split']} | {r['n']} | {r['accuracy']:.4f} | "
                     f"{r['macro_f1']:.4f} | {r['top5']:.4f} | {r['latency_ms']:.1f} |")
    lines += ["", "Notes:",
              "- jackfurby_test is synthetic (same digital design, different generated images).",
              "- real52_test is real photographs but each class folder repeats one physical card;",
              "  it measures cross-source robustness, not unseen-physical-card generalisation.",
              "- Template scores are similarity values, not calibrated probabilities."]
    (out_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
