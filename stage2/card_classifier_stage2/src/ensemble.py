# -*- coding: utf-8 -*-
"""Stacking / decision-tree ensemble of template, HOG+SVM and CNN.

The meta-model does not see the image pixels.  For every candidate label it gets
each base model's score/rank, how many models vote for the candidate, the
template design similarity and image quality.  A shallow decision tree learns
which candidate to trust and when to reject.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from .classifier import BaseCardClassifier, create_classifier

MODELS = ("template", "hog_svm", "cnn")
FEATURE_NAMES = []
for _m in MODELS:
    FEATURE_NAMES += [f"{_m}_score", f"{_m}_rank", f"{_m}_top1_score", f"{_m}_margin"]
FEATURE_NAMES += ["votes", "design_similarity", "detected", "blurry", "lap_var_norm"]


def _ticket(candidate: str, results: Dict[str, dict], quality: dict) -> List[float]:
    row = []
    for m in MODELS:
        r = results[m]
        top = r.get("top5", [])
        labels = [x[0] for x in top]
        score = next((float(v) for k, v in top if k == candidate), 0.0)
        rank = labels.index(candidate) + 1 if candidate in labels else 6
        row += [score, float(rank), float(r.get("score", 0.0)),
                float(r.get("margin", 0.0))]
    votes = sum(1 for m in MODELS if results[m].get("best_label") == candidate)
    row += [float(votes), float(results["template"].get("score", 0.0)),
            1.0 if results["template"].get("detected") else 0.0,
            1.0 if quality.get("blurry") else 0.0,
            min(1.0, float(quality.get("laplacian_var", 0.0)) / 200.0)]
    return row


def candidates_for(results: Dict[str, dict]) -> List[str]:
    out = []
    for m in MODELS:
        label = results[m].get("best_label", "")
        if label and label not in out:
            out.append(label)
    return out


class EnsembleClassifier(BaseCardClassifier):
    name = "ensemble"

    def __init__(self, model_dir, meta_path=None, threshold: float = 0.5,
                 min_votes: int = 2):
        import joblib

        model_dir = Path(model_dir)
        meta_path = Path(meta_path) if meta_path else model_dir / "ensemble.joblib"
        self.models = {
            "template": create_classifier("template", template_dir=model_dir.parent / "data" / "templates",
                                          threshold=None),
            "hog_svm": create_classifier("hog", model_path=model_dir / "hog_svm.joblib", threshold=None),
            "cnn": create_classifier("cnn", model_path=model_dir / "cnn.pt", threshold=None),
        }
        bundle = joblib.load(meta_path)
        self.tree = bundle["tree"]
        self.feature_names = bundle.get("feature_names", FEATURE_NAMES)
        self.threshold = float(bundle.get("threshold", threshold))
        self.min_votes = int(bundle.get("min_votes", min_votes))

    def predict(self, image) -> Dict:
        from .image_utils import image_quality

        card, info = self._load(image)
        quality = image_quality(image)
        results = {m: self.models[m].predict(image) for m in MODELS}
        cands = candidates_for(results)
        if not cands:
            raise RuntimeError("ensemble received no candidates")
        X = np.array([_ticket(c, results, quality) for c in cands], dtype=np.float32)
        probs = self.tree.predict_proba(X)
        # class 1 is "this candidate is correct"; handle a constant tree too.
        if probs.shape[1] == 1:
            p1 = np.ones(len(cands)) if int(self.tree.classes_[0]) == 1 else np.zeros(len(cands))
        else:
            p1 = probs[:, list(self.tree.classes_).index(1)] if 1 in self.tree.classes_ else probs[:, -1]
        order = np.argsort(-p1)
        ranked = [(cands[i], float(p1[i])) for i in order]
        best, best_p = ranked[0]
        votes = sum(1 for m in MODELS if results[m].get("best_label") == best)
        # Fault-tolerance fallback: if the design is known (template similarity
        # high) and HOG is very confident, trust HOG.  This avoids a shallow tree
        # discarding a correctly classified sample when the other two models are
        # uncertain.  It is skipped for unseen designs, where HOG is overconfident.
        hog = results["hog_svm"]
        design = results["template"]
        if (design.get("score", 0.0) >= 0.55 and hog.get("score", 0.0) >= 0.90
                and hog.get("margin", 0.0) >= 0.25):
            best = hog.get("best_label", best)
            best_p = max(best_p, float(hog.get("score", 0.0)))
            votes = sum(1 for m in MODELS if results[m].get("best_label") == best)
        accepted = best_p >= self.threshold and votes >= self.min_votes
        result = self._result(card, info, dict(ranked), threshold=None,
                              corner=results["hog_svm"].get("corner", ""))
        result["label"] = best if accepted else "UNKNOWN"
        result["best_label"] = best
        result["score"] = best_p
        result["score_kind"] = "meta probability"
        result["accepted"] = accepted
        result["votes"] = votes
        result["components"] = {
            m: {"label": results[m].get("best_label"),
                "score": float(results[m].get("score", 0.0)),
                "margin": float(results[m].get("margin", 0.0))}
            for m in MODELS
        }
        result["quality"] = quality
        return result
