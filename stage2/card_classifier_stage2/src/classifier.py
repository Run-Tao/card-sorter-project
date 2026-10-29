# -*- coding: utf-8 -*-
"""Unified classifier interface: template matching, HOG+SVM, small CNN.

All classifiers accept either an image path or a BGR numpy array and return a
dictionary with the same keys, so evaluation code can compare them fairly:

    image, label, best_label, score, corner, second_label, second_score,
    margin, classifier, top5, detected, quad

``label`` is "UNKNOWN" when a rejection threshold is configured and the best
score is below it; ``best_label`` always contains the top candidate.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import cv2
import numpy as np

from .card_labels import is_valid_label
from .image_utils import (CANONICAL_SIZE, corner_roi, normalize_card,
                          normalize_card_color, normalize_roi, read_image,
                          rectify_card)
from .features import extract_features


def _softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    x = x - np.max(x)
    ex = np.exp(x)
    return ex / max(ex.sum(), 1e-12)


class BaseCardClassifier:
    name = "base"

    def predict(self, image) -> Dict:
        raise NotImplementedError

    def _load(self, image) -> Tuple[np.ndarray, dict]:
        if isinstance(image, (str, Path)):
            arr = read_image(image)
            image_name = str(image)
        elif isinstance(image, np.ndarray):
            arr = image
            image_name = "<array>"
        else:
            raise TypeError(f"unsupported image type: {type(image)!r}")
        # Already-rectified inputs (the processed dataset and templates) must not
        # be re-detected: a second warp changes the corner geometry and makes
        # template/query features inconsistent.
        if arr.shape[1] == CANONICAL_SIZE[0] and arr.shape[0] == CANONICAL_SIZE[1]:
            return arr, {"image": image_name, "detected": True,
                         "quad": None, "method": "already_canonical"}
        card, info = rectify_card(arr)
        return card, {"image": image_name, **info}

    def _result(self, card: np.ndarray, info: dict, scores: Dict[str, float],
                top_k: int = 5, threshold: Optional[float] = None,
                corner: str = "") -> Dict:
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked:
            raise RuntimeError("classifier produced no scores")
        best_label, best_score = ranked[0]
        second_label, second_score = ranked[1] if len(ranked) > 1 else ("", -1.0)
        label = best_label if threshold is None or best_score >= threshold else "UNKNOWN"
        return {
            "image": info.get("image", ""),
            "label": label,
            "best_label": best_label,
            "score": float(best_score),
            "corner": corner,
            "second_label": second_label,
            "second_score": float(second_score),
            "margin": float(best_score - second_score),
            "classifier": self.name,
            "top5": [[k, float(v)] for k, v in ranked[:top_k]],
            "detected": bool(info.get("detected", False)),
            "quad": info.get("quad"),
        }


class TemplateCardClassifier(BaseCardClassifier):
    """Corner template matching with normalized cross-correlation.

    Templates are canonical rectified cards; only the upper-left corner ROI is
    stored, and the query is compared against both the TL and the 180-degree
    rotated BR corner.  The score is a similarity, NOT a calibrated probability.
    """

    name = "template"

    def __init__(self, template_dir, threshold: Optional[float] = 0.35,
                 roi_size: Tuple[int, int] = (128, 128),
                 equalize: bool = True, method: str = "ccoeff",
                 roi_x2: float = 0.30, roi_y2: float = 0.24):
        self.template_dir = Path(template_dir)
        self.threshold = None if threshold is None else float(threshold)
        self.roi_size = roi_size
        self.equalize = bool(equalize)
        self.method = method
        self.roi_x2 = float(roi_x2)
        self.roi_y2 = float(roi_y2)
        self.templates: Dict[str, List[np.ndarray]] = {}
        self.custom_labels: set = set()
        self._load_templates()

    def _load_templates(self):
        if not self.template_dir.exists():
            raise FileNotFoundError(f"template directory not found: {self.template_dir}")
        allowed = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        bad = []
        for path in sorted(self.template_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            # Template filenames are AS.png, 10H_custom_123.png, etc.  The first
            # underscore-separated field is the label; this allows custom
            # templates for unseen card designs.
            label = path.stem.split("_")[0].upper()
            if not is_valid_label(label):
                bad.append(path.name)
                continue
            card = read_image(path)
            if card.shape[1] != CANONICAL_SIZE[0] or card.shape[0] != CANONICAL_SIZE[1]:
                card, _ = rectify_card(card)
            # Rectification has a 0/180-degree ambiguity (opposite corners carry
            # the same index).  Store the TL and the 180-rotated BR crop; the
            # query does the same, so matching is invariant to that ambiguity.
            rois = []
            for corner in ("tl", "br"):
                roi = corner_roi(card, corner, rotate_180=(corner == "br"),
                                 x2=self.roi_x2, y2=self.roi_y2)
                rois.append(normalize_roi(roi, size=self.roi_size,
                                          equalize=self.equalize))
            self.templates.setdefault(label, []).extend(rois)
            if "_custom_" in path.stem.lower():
                self.custom_labels.add(label)
        if bad:
            print(f"[WARN] ignored {len(bad)} template file(s) with invalid labels: {bad[:5]}")
        if not self.templates:
            raise RuntimeError(
                f"no valid templates in {self.template_dir}; expected files like AS.png / 10H.jpg")

    def _score(self, query: np.ndarray, template: np.ndarray) -> float:
        if query.shape != template.shape:
            template = cv2.resize(template, (query.shape[1], query.shape[0]))
        if self.method == "sqdiff":
            res = cv2.matchTemplate(query, template, cv2.TM_SQDIFF_NORMED)
            score = 1.0 - float(res[0, 0])
        elif self.method == "ccoeff":
            res = cv2.matchTemplate(query, template, cv2.TM_CCOEFF_NORMED)
            score = float(res[0, 0])
        else:
            raise ValueError("method must be 'ccoeff' or 'sqdiff'")
        if not np.isfinite(score):
            return -1.0
        return score

    def predict(self, image) -> Dict:
        card, info = self._load(image)
        queries = []
        for corner in ("tl", "br"):
            roi = corner_roi(card, corner, rotate_180=(corner == "br"),
                             x2=self.roi_x2, y2=self.roi_y2)
            queries.append((corner, normalize_roi(
                roi, size=self.roi_size, equalize=self.equalize)))
        scores: Dict[str, float] = {}
        best_corner = ""
        for label, templates in self.templates.items():
            for corner, query in queries:
                for template in templates:
                    sc = self._score(query, template)
                    if label not in scores or sc > scores[label]:
                        scores[label] = sc
                        best_corner = corner
        return self._result(card, info, scores, threshold=self.threshold,
                            corner=best_corner)


def _rot180(image: np.ndarray) -> np.ndarray:
    return cv2.rotate(image, cv2.ROTATE_180)


def _rotations(card: np.ndarray) -> list:
    """0/90/180/270 rotations for orientation-invariant TTA."""
    return [
        card,
        cv2.rotate(card, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(card, cv2.ROTATE_180),
        cv2.rotate(card, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]


class HOGSVMClassifier(BaseCardClassifier):
    """HOG features + linear SVM (scikit-learn), loaded from a joblib bundle."""

    name = "hog_svm"

    def __init__(self, model_path, threshold: Optional[float] = None):
        import joblib

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"HOG/SVM model not found: {self.model_path}")
        bundle = joblib.load(self.model_path)
        self.model = bundle["model"]
        self.classes = [str(x) for x in bundle["classes"]]
        self.mode = bundle.get("mode", "full")
        self.image_size = tuple(bundle.get("image_size", (64, 96)))
        self.equalize = bool(bundle.get("equalize", False))
        self.threshold = None if threshold is None else float(threshold)

    def predict(self, image) -> Dict:
        card, info = self._load(image)
        scores: Dict[str, float] = {}
        for variant in _rotations(card):
            feat = extract_features(variant, mode=self.mode, image_size=self.image_size,
                                    equalize=self.equalize).reshape(1, -1)
            if hasattr(self.model, "predict_proba"):
                proba = np.asarray(self.model.predict_proba(feat)[0], dtype=np.float64)
                proba = np.nan_to_num(proba, nan=0.0, posinf=0.0, neginf=0.0)
                if proba.sum() <= 0:
                    proba = np.full(len(proba), 1.0 / max(len(proba), 1))
                else:
                    proba = proba / proba.sum()
                from .card_labels import index_to_label
                classes = [index_to_label(int(c)) if isinstance(c, (int, np.integer))
                           else str(c) for c in self.model.classes_]
                current = {c: float(p) for c, p in zip(classes, proba)}
            else:
                dec = np.asarray(self.model.decision_function(feat)).reshape(-1)
                if len(self.classes) == 2 and dec.size == 1:
                    dec = np.array([-dec[0], dec[0]])
                proba = _softmax(dec)
                current = {c: float(p) for c, p in zip(self.classes, proba)}
            for k, v in current.items():
                scores[k] = max(scores.get(k, -1.0), v)
        # confidence here is a softmax over SVM decision values, not calibrated
        return self._result(card, info, scores, threshold=self.threshold)


class CNNCardClassifier(BaseCardClassifier):
    """Small CNN trained in this project; PyTorch is imported lazily."""

    name = "cnn"

    def __init__(self, model_path, threshold: Optional[float] = None):
        import torch

        from .model_cnn import build_model

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"CNN checkpoint not found: {self.model_path}")
        self.torch = torch
        torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
        ckpt = torch.load(str(self.model_path), map_location="cpu", weights_only=False)
        self.labels = [str(x) for x in ckpt["labels"]]
        self.image_size = tuple(ckpt.get("image_size", (64, 96)))
        self.mean = float(ckpt.get("mean", 0.5))
        self.std = float(ckpt.get("std", 0.5))
        self.model = build_model(num_classes=len(self.labels))
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.threshold = None if threshold is None else float(threshold)

    def _tensor(self, card: np.ndarray):
        rgb = normalize_card_color(card, size=self.image_size)
        x = rgb.astype(np.float32) / 255.0
        x = (x - self.mean) / max(self.std, 1e-6)
        return self.torch.from_numpy(np.transpose(x, (2, 0, 1))).unsqueeze(0)

    def predict(self, image) -> Dict:
        card, info = self._load(image)
        scores: Dict[str, float] = {}
        with self.torch.no_grad():
            for variant in _rotations(card):
                logits = self.model(self._tensor(variant))[0]
                proba = self.torch.softmax(logits, dim=0).cpu().numpy()
                for c, p in zip(self.labels, proba):
                    scores[c] = max(scores.get(c, -1.0), float(p))
        return self._result(card, info, scores, threshold=self.threshold)


def create_classifier(kind: str, **kwargs) -> BaseCardClassifier:
    kind = kind.lower()
    if kind in ("template", "tpl"):
        return TemplateCardClassifier(**kwargs)
    if kind in ("hog", "hog_svm", "svm"):
        return HOGSVMClassifier(**kwargs)
    if kind in ("cnn", "deep"):
        return CNNCardClassifier(**kwargs)
    if kind in ("ensemble", "stack", "vote"):
        from .ensemble import EnsembleClassifier
        return EnsembleClassifier(**kwargs)
    raise ValueError(f"unknown classifier kind: {kind}")
