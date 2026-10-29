# -*- coding: utf-8 -*-
"""Registered user-shape templates.

A full-image correlation matcher for cards the user has explicitly registered
(examples).  This is a one-shot enrolment path, not a general cross-design
model; it makes the provided demo cards reproducible without retraining.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np


class CustomTemplateMatcher:
    def __init__(self, folder: Path, threshold: float = 0.82):
        self.folder = Path(folder)
        self.threshold = float(threshold)
        self.items = []
        if self.folder.exists():
            for p in sorted(self.folder.glob("*.png")):
                label = p.stem.split("_")[0].upper()
                im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                if im is None:
                    continue
                self.items.append((label, cv2.resize(im, (210, 294))))

    def predict(self, image: np.ndarray) -> Optional[dict]:
        if not self.items or image is None:
            return None
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        q = cv2.resize(gray, (210, 294))
        best_label, best = "", -1.0
        for label, tpl in self.items:
            res = cv2.matchTemplate(q, tpl, cv2.TM_CCOEFF_NORMED)
            score = float(res[0, 0])
            if score > best:
                best, best_label = score, label
        if best < self.threshold:
            return None
        return {"label": best_label, "best_label": best_label,
                "score": best, "top5": [[best_label, best]],
                "corner": "full", "detected": True, "quad": None,
                "method": "user_template"}
