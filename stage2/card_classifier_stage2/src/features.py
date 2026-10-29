# -*- coding: utf-8 -*-
"""Feature extraction shared by training and inference."""

from __future__ import annotations

from typing import Tuple

import numpy as np
from skimage.feature import hog

from .image_utils import corner_roi, normalize_card, normalize_roi

HOG_KW = dict(
    orientations=9,
    pixels_per_cell=(8, 8),
    cells_per_block=(2, 2),
    block_norm="L2-Hys",
    feature_vector=True,
)


def extract_features(card_bgr: np.ndarray,
                     mode: str = "full",
                     image_size: Tuple[int, int] = (64, 96),
                     equalize: bool = False) -> np.ndarray:
    """Return a 1-D HOG feature vector for a rectified card.

    mode = "full"   : full card resized to (w=64, h=96)
    mode = "corner" : upper-left corner ROI normalized to 64x64
    """
    if mode == "full":
        gray = normalize_card(card_bgr, size=image_size, equalize=equalize)
    elif mode == "corner":
        roi = corner_roi(card_bgr, "tl")
        gray = normalize_roi(roi, size=(64, 64), equalize=equalize)
    else:
        raise ValueError("mode must be 'full' or 'corner'")
    return hog(gray, **HOG_KW).astype(np.float32)


def batch_features(cards, mode: str = "full", image_size: Tuple[int, int] = (64, 96),
                   equalize: bool = False) -> np.ndarray:
    return np.stack([extract_features(c, mode=mode, image_size=image_size,
                                      equalize=equalize) for c in cards])
