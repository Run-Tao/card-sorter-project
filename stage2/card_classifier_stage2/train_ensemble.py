# -*- coding: utf-8 -*-
"""Train/evaluate the decision-tree ensemble on val, then report test metrics."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report
from sklearn.tree import DecisionTreeClassifier

from src.classifier import create_classifier
from src.ensemble import FEATURE_NAMES, MODELS, _ticket, candidates_for
from src.evaluate import collect_items
from src.image_utils import image_quality

ROOT = Path(__file__).resolve().parent


def build_rows(models, items):
    X, y, meta = [], [], []
    for path, truth in items:
        try:
            img = cv2_read(path)
        except Exception:
            continue
        results = {m: models[m].predict(img) for m in MODELS}
        quality = image_quality(img)
        for cand in candidates_for(results):
            X.append(_ticket(cand, results, quality))
            y.append(1 if cand == truth else 0)
            meta.append((str(path), truth, cand))
    return np.asarray(X, np.float32), np.asarray(y), meta


def cv2_read(path):
    from src.image_utils import read_image
    return read_image(path)


def evaluate(models, tree, items):
    ok = accepted = accepted_ok = 0
    rows = []
    for path, truth in items:
        img = cv2_read(path)
        results = {m: models[m].predict(img) for m in MODELS}
        cands = candidates_for(results)
        X = np.asarray([_ticket(c, results, image_quality(img)) for c in cands], np.float32)
        probs = tree.predict_proba(X)
        p1 = probs[:, list(tree.classes_).index(1)] if 1 in tree.classes_ else probs[:, -1]
        i = int(np.argmax(p1))
        label = cands[i]
        votes = sum(1 for m in MODELS if results[m].get("best_label") == label)
        hog = results["hog_svm"]
        if (results["template"].get("score", 0.0) >= 0.55 and hog.get("score", 0.0) >= 0.90
                and hog.get("margin", 0.0) >= 0.25):
            label = hog.get("best_label", label)
            votes = sum(1 for m in MODELS if results[m].get("best_label") == label)
        acc = bool(p1[i] >= 0.5 and votes >= 2) or (
            results["template"].get("score", 0.0) >= 0.55 and hog.get("score", 0.0) >= 0.90
            and hog.get("margin", 0.0) >= 0.25)
        ok += int(label == truth and acc)
        accepted += int(acc)
        accepted_ok += int(acc and label == truth)
        rows.append({"path": str(path), "truth": truth, "pred": label,
                     "prob": float(p1[i]), "accepted": acc, "votes": votes,
                     "correct": label == truth and acc})
    return {
        "n": len(items), "accuracy": ok / len(items),
        "coverage": accepted / len(items),
        "accepted_accuracy": accepted_ok / accepted if accepted else 0.0,
        "rows": rows,
    }


def main():
    models = {
        "template": create_classifier("template", template_dir=ROOT / "data/templates", threshold=None),
        "hog_svm": create_classifier("hog", model_path=ROOT / "models/hog_svm.joblib", threshold=None),
        "cnn": create_classifier("cnn", model_path=ROOT / "models/cnn.pt", threshold=None),
    }
    val = collect_items(ROOT / "data/processed/jackfurby/val")
    print(f"[ensemble] val={len(val)} ...")
    X, y, _ = build_rows(models, val)
    print(f"[ensemble] meta samples={len(y)} positives={int(y.sum())}")
    tree = DecisionTreeClassifier(max_depth=6, min_samples_leaf=8,
                                  class_weight="balanced", random_state=42)
    tree.fit(X, y)
    bundle = {"tree": tree, "feature_names": FEATURE_NAMES,
              "threshold": 0.5, "min_votes": 2}
    (ROOT / "models").mkdir(exist_ok=True)
    joblib.dump(bundle, ROOT / "models/ensemble.joblib")
    out = {"meta_accuracy": float(tree.score(X, y)), "splits": {}}
    for name, folder in (("jackfurby_test", ROOT / "data/processed/jackfurby/test"),
                         ("real52_test", ROOT / "data/processed/real52/all")):
        items = collect_items(folder)
        print(f"[ensemble] eval {name} ({len(items)}) ...")
        res = evaluate(models, tree, items)
        res.pop("rows", None)
        out["splits"][name] = res
        print(name, {k: round(v, 4) if isinstance(v, float) else v for k, v in res.items()})
    (ROOT / "outputs/ensemble_eval.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
