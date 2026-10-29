# -*- coding: utf-8 -*-
"""Choose rejection thresholds on the validation split and report the trade-off.

The threshold is selected on data/processed/jackfurby/val (never test), then
applied unchanged to the synthetic and real test sets.  This is a coverage
vs. accepted-accuracy trade-off, not a calibrated probability guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.classifier import create_classifier
from src.evaluate import collect_items


def run_model(name, clf, root: Path):
    val = collect_items(root / "data/processed/jackfurby/val")
    tests = {
        "jackfurby_test": collect_items(root / "data/processed/jackfurby/test"),
        "real52_test": collect_items(root / "data/processed/real52/all"),
    }
    def score(items):
        out = []
        for p, t in items:
            r = clf.predict(p)
            out.append({"score": float(r["score"]),
                        "correct": r["best_label"] == t,
                        "pred": r["best_label"], "truth": t})
        return out
    val_rows = score(val)
    scores = np.array([r["score"] for r in val_rows])
    correct = np.array([r["correct"] for r in val_rows], dtype=float)
    result = {"model": name, "val_size": len(val_rows),
              "val_accuracy": float(correct.mean()), "thresholds": {}}
    for coverage in (0.99, 0.95, 0.90):
        thr = float(np.quantile(scores, 1.0 - coverage))
        accepted = scores >= thr
        acc = float(correct[accepted].mean()) if accepted.any() else 0.0
        result["thresholds"][f"coverage_{coverage:.2f}"] = {
            "threshold": thr,
            "val_coverage": float(accepted.mean()),
            "val_accepted_accuracy": acc,
        }
    chosen = result["thresholds"]["coverage_0.95"]["threshold"]
    result["chosen_threshold"] = chosen
    for test_name, items in tests.items():
        rows = score(items)
        s = np.array([r["score"] for r in rows])
        c = np.array([r["correct"] for r in rows], dtype=float)
        accepted = s >= chosen
        result[test_name] = {
            "n": len(rows),
            "coverage": float(accepted.mean()),
            "accepted_accuracy": float(c[accepted].mean()) if accepted.any() else 0.0,
            "all_accuracy": float(c.mean()),
        }
    return result


def main():
    root = Path(".").resolve()
    models = []
    if (root / "data/templates").exists():
        models.append(("template", create_classifier(
            "template", template_dir=root / "data/templates", threshold=None)))
    if (root / "models/hog_svm.joblib").exists():
        models.append(("hog_svm", create_classifier(
            "hog", model_path=root / "models/hog_svm.joblib", threshold=None)))
    if (root / "models/cnn.pt").exists():
        models.append(("cnn", create_classifier(
            "cnn", model_path=root / "models/cnn.pt", threshold=None)))
    if not models:
        raise RuntimeError("no models found")
    out = {}
    for name, clf in models:
        print(f"[calib] {name} ...")
        out[name] = run_model(name, clf, root)
    out_dir = root / "outputs/calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "thresholds.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Rejection threshold calibration", "",
             "Threshold chosen on `jackfurby_val` for 95% coverage, then applied unchanged.",
             "", "| model | threshold | val cov | val accepted acc | synthetic cov | synthetic acc | real cov | real acc |",
             "|---|---|---|---|---|---|---|---|"]
    for name, r in out.items():
        t = r["thresholds"]["coverage_0.95"]
        s = r["jackfurby_test"]
        rr = r["real52_test"]
        lines.append(f"| {name} | {r['chosen_threshold']:.4f} | {t['val_coverage']:.3f} | "
                     f"{t['val_accepted_accuracy']:.4f} | {s['coverage']:.3f} | "
                     f"{s['accepted_accuracy']:.4f} | {rr['coverage']:.3f} | "
                     f"{rr['accepted_accuracy']:.4f} |")
    lines += ["", "Scores are similarity/softmax values, not calibrated probabilities.",
              "Coverage = fraction of cards accepted; rejected cards should go to a review bin."]
    (out_dir / "thresholds.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
