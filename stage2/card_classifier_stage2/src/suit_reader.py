# -*- coding: utf-8 -*-
"""Suit-only recognition (4 classes) for the revised research goal.

Localization is reported explicitly (auto quadrilateral or close-up full-frame
fallback).  The suit classifier uses the corner symbol templates and colour
family; rank is intentionally ignored.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .corner_semantic import CornerSemanticReader
from .image_utils import CANONICAL_SIZE, read_image, rectify_card

SUIT_NAME = {"S": "黑桃", "H": "红心", "D": "方块", "C": "梅花"}


class SuitReader:
    name = "suit"

    def __init__(self):
        self.corner = CornerSemanticReader()

    def predict(self, image) -> dict:
        arr = read_image(image) if isinstance(image, (str, Path)) else image
        if arr is None:
            raise ValueError("empty image")
        suit, conf = self.corner._suit_from_original(arr)
        if not suit and arr.shape[1] == CANONICAL_SIZE[0] and arr.shape[0] == CANONICAL_SIZE[1]:
            # canonical card: use a rectified corner crop
            suit, conf = self.corner._suit_from_original(arr)
        card, info = rectify_card(arr)
        if info.get("detected"):
            # for already-good full-card photos, the same corner template works
            s2, c2 = self.corner._suit_from_original(arr)
            if s2 and c2 > conf:
                suit, conf = s2, c2
        localized = bool(info.get("detected"))
        return {
            "label": suit if suit else "UNKNOWN",
            "best_label": suit,
            "suit": suit,
            "suit_name": SUIT_NAME.get(suit, ""),
            "score": float(conf),
            "accepted": bool(suit and conf >= 0.45),
            "localized": localized,
            "localization": info.get("method", "full_image_fallback"),
            "detected": localized,
            "quad": info.get("quad"),
            "top5": [[suit, float(conf)]] if suit else [],
            "method": "suit_only",
            "rectified": card,
        }
