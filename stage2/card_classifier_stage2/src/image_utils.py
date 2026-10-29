# -*- coding: utf-8 -*-
"""Image I/O, card detection / rectification, corner ROI and preview helpers.

The canonical rectified card is 210 x 294 pixels (aspect 63.5:88.9 ~= 0.714).
All classifiers share this canonical representation.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import cv2
import numpy as np

CANONICAL_SIZE = (210, 294)  # (width, height)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# --------------------------------------------------------------------------- I/O
def read_image(path) -> np.ndarray:
    """Read a BGR image and support non-ASCII Windows paths.

    Raises FileNotFoundError / ValueError with an actionable message instead of
    returning None (which is the most common source of confusing downstream
    failures).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"image not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"image file is empty: {path}")
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"cannot decode image (unsupported or corrupted): {path}")
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        # Transparent PNG card cut-outs: composite on white, otherwise the
        # transparent background is read as black and localization fails.
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        bgr = image[:, :, :3].astype(np.float32)
        image = (bgr * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return image


def save_image(path, image: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower() or ".png"
    ok, encoded = cv2.imencode(suffix, image)
    if not ok:
        raise ValueError(f"cannot encode image as {suffix}: {path}")
    encoded.tofile(str(path))


# ------------------------------------------------------------------- geometry
def order_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    """Order 4 points around the card as TL, TR, BR, BL.

    Sorting by x+y fails for cards rotated near 45 degrees (two corners tie).
    The centroid-angle sort is robust for arbitrary rotations; we then rotate
    the sequence so it starts at the top-left-most corner.
    """
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
    pts = pts[np.argsort(angles)]          # clockwise in image coordinates
    start = int(np.argmin(pts.sum(axis=1)))
    pts = np.roll(pts, -start, axis=0)
    return pts.astype(np.float32)


def _quad_score(quad: np.ndarray, image_area: float,
                small_bgr: Optional[np.ndarray] = None) -> float:
    """Score a quadrilateral as a playing-card candidate (higher is better)."""
    area = abs(cv2.contourArea(quad.astype(np.float32)))
    if area <= 0 or image_area <= 0:
        return -1.0
    rect = cv2.minAreaRect(quad.astype(np.float32))
    (w, h) = rect[1]
    if min(w, h) < 15:
        return -1.0
    long_side, short_side = max(w, h), min(w, h)
    aspect = long_side / max(short_side, 1e-6)
    area_ratio = area / image_area
    rect_area = w * h
    rectangularity = area / max(rect_area, 1e-6)
    # Reject the whole frame / huge background blobs and implausible shapes.
    if area_ratio < 0.012 or area_ratio > 0.85:
        return -1.0
    if aspect < 1.15 or aspect > 1.80:
        return -1.0
    aspect_score = math.exp(-((aspect - 1.42) / 0.22) ** 2)
    area_score = min(area_ratio, 0.45) / 0.45

    # Interior appearance: a card is a bright, low-saturation region.  This is
    # what separates a small white card from a large grey table/background.
    bright, sat = 0.0, 0.0
    if small_bgr is not None:
        mask = np.zeros(small_bgr.shape[:2], np.uint8)
        cv2.fillPoly(mask, [quad.astype(np.int32)], 255)
        hsv = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2][mask > 0]
        s = hsv[:, :, 1][mask > 0]
        if v.size:
            mean_v, mean_s = float(v.mean()), float(s.mean())
            bright = max(0.0, min(1.0, (mean_v - 145.0) / 85.0))
            sat = max(0.0, min(1.0, (80.0 - mean_s) / 55.0))
            if mean_v < 135:
                bright = -1.0

    score = 2.0 * area_score + 1.0 * rectangularity + 2.0 * aspect_score \
        + 3.0 * bright + 1.0 * sat
    # A card that fills >60% of the frame is possible, but a full-frame contour
    # is usually the background; gently penalise the ambiguous 0.6-0.85 range.
    if area_ratio > 0.60:
        score -= (area_ratio - 0.60) * 6.0
    # Canonical inputs are portrait (63.5x88.9).  A landscape candidate is
    # usually a background strip; allow it only if it is clearly the best.
    ordered = order_points(quad)
    width = np.linalg.norm(ordered[1] - ordered[0])
    height = np.linalg.norm(ordered[2] - ordered[1])
    if width > height:
        score -= 1.5
    return score


def _quads_from_mask(mask: np.ndarray, image_area: float,
                     approx_eps: float = 0.02) -> list[np.ndarray]:
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
        if cv2.contourArea(cnt) < image_area * 0.03:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, approx_eps * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            out.append(approx.reshape(4, 2).astype(np.float32))
        else:
            rect = cv2.minAreaRect(cnt)
            box = cv2.boxPoints(rect).astype(np.float32)
            out.append(box)
    return out


def detect_card_quad(image: np.ndarray) -> Optional[np.ndarray]:
    """Find a card quadrilateral in a photo.

    Tries several complementary cues (Canny edges / bright-low-saturation card
    mask / Otsu threshold) and returns the best-scoring 4-point quadrilateral
    in original image coordinates, or None when no plausible card is found.
    """
    if image is None or image.size == 0:
        return None
    h, w = image.shape[:2]
    scale = min(1.0, 900.0 / max(h, w))
    small = cv2.resize(image, (int(w * scale), int(h * scale)),
                       interpolation=cv2.INTER_AREA) if scale < 1 else image.copy()
    sh, sw = small.shape[:2]
    image_area = float(sh * sw)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    candidates: list[np.ndarray] = []

    # 1) bright, low-saturation card mask (works for white cards on dark tables)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask_white = cv2.inRange(hsv, (0, 0, 160), (180, 70, 255))
    candidates += _quads_from_mask(mask_white, image_area)
    mask_bright = cv2.inRange(hsv, (0, 0, 200), (180, 55, 255))
    candidates += _quads_from_mask(mask_bright, image_area)

    # 2) Otsu threshold (both polarities)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates += _quads_from_mask(otsu, image_area)
    candidates += _quads_from_mask(cv2.bitwise_not(otsu), image_area)

    # 3) Canny edges (two thresholds: low for low-contrast cards)
    edges = cv2.Canny(gray, 30, 90)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    candidates += _quads_from_mask(edges, image_area, approx_eps=0.02)
    edges2 = cv2.Canny(gray, 60, 160)
    edges2 = cv2.dilate(edges2, np.ones((3, 3), np.uint8), iterations=1)
    candidates += _quads_from_mask(edges2, image_area, approx_eps=0.02)

    # 4) adaptive threshold on a CLAHE-enhanced gray image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    adaptive = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 51, -8)
    candidates += _quads_from_mask(adaptive, image_area)

    best, best_score = None, -1.0
    best_ratio = 0.0
    large_best, large_score, large_ratio = None, -1.0, 0.0
    for quad in candidates:
        score = _quad_score(quad, image_area, small)
        area_ratio = abs(cv2.contourArea(quad.astype(np.float32))) / image_area
        if score > best_score:
            best, best_score, best_ratio = quad, score, area_ratio
        # A close-up card is usually a large quadrilateral.  Internal artwork /
        # text blocks can score higher on brightness and win by mistake, so keep
        # a large-card candidate as a fallback when the top pick is tiny.
        if 0.18 <= area_ratio <= 0.88 and score > large_score:
            large_best, large_score, large_ratio = quad, score, area_ratio
    if (best is None or (best_ratio < 0.18 and large_best is not None
                         and large_score >= best_score * 0.80)):
        best, best_score, best_ratio = large_best, large_score, large_ratio
    # Close-up cards often fill >85% of the frame, which the normal scoring
    # rejects.  Use the largest bright, low-saturation contour as a last resort.
    if best is None or best_ratio < 0.35:
        contours, _ = cv2.findContours(mask_white, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            ratio = cv2.contourArea(cnt) / image_area
            if ratio < 0.35:
                continue
            rect = cv2.minAreaRect(cnt)
            ww, hh = rect[1]
            if min(ww, hh) < 20:
                continue
            aspect = max(ww, hh) / max(1.0, min(ww, hh))
            if not (1.15 <= aspect <= 1.85):
                continue
            best = cv2.boxPoints(rect).astype(np.float32)
            best_ratio = ratio
            break
    if best is None or best_score <= 0:
        return None
    best = order_points(best)
    return best / max(scale, 1e-6)


def rectify_card_from_points(image: np.ndarray, points: Sequence[Sequence[float]],
                             size: Tuple[int, int] = CANONICAL_SIZE,
                             margin_ratio: float = 0.0) -> np.ndarray:
    """Warp the card given 4 corners in TL,TR,BR,BL order.

    ``points`` may be in any order; they are re-ordered defensively.
    """
    src = order_points(points)
    w, h = size
    if margin_ratio > 0:
        mx, my = int(w * margin_ratio), int(h * margin_ratio)
        dst = np.array([[mx, my], [w - 1 - mx, my],
                        [w - 1 - mx, h - 1 - my], [mx, h - 1 - my]], dtype=np.float32)
    else:
        dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
                       dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(image, matrix, (w, h),
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)


def rectify_card(image: np.ndarray, size: Tuple[int, int] = CANONICAL_SIZE,
                 margin_ratio: float = 0.02) -> Tuple[np.ndarray, dict]:
    """Detect and rectify a card; fall back to resizing the whole image.

    Returns (rectified_image, info).  ``info["detected"]`` tells whether a
    quadrilateral was actually found.  The fallback keeps the pipeline running
    on already-cropped card images, but evaluation must report detection rate.
    """
    quad = detect_card_quad(image)
    if quad is not None:
        return rectify_card_from_points(image, quad, size, margin_ratio), {
            "detected": True,
            "quad": quad.tolist(),
            "method": "quad",
        }
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, 165), (180, 85, 255))
    coverage = float((white > 0).mean())
    if coverage > 0.45:
        # A close-up card fills the frame.  Report this explicitly instead of
        # pretending detection failed or presenting an interior-artwork quad.
        h, w = image.shape[:2]
        return cv2.resize(image, size, interpolation=cv2.INTER_AREA), {
            "detected": True,
            "quad": [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
            "method": "full_frame_closeup",
            "white_coverage": round(coverage, 3),
        }
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA), {
        "detected": False,
        "quad": None,
        "method": "full_image_fallback",
    }


# ---------------------------------------------------------------------- ROIs
def corner_roi(card: np.ndarray, corner: str = "tl",
               x1: float = 0.02, x2: float = 0.34,
               y1: float = 0.02, y2: float = 0.30,
               rotate_180: bool = False) -> np.ndarray:
    """Crop one of the four corners from a rectified card image.

    The rectification pipeline has an unknown 0/90/180/270 orientation, so
    callers that need orientation invariance should sample all four corners and
    compare both 0-degree and 180-degree rotated versions.  Set
    ``rotate_180=True`` to get the rotated crop directly.
    """
    if card is None or card.size == 0:
        raise ValueError("empty card image")
    h, w = card.shape[:2]
    xa, xb = sorted((int(w * x1), int(w * x2)))
    ya, yb = sorted((int(h * y1), int(h * y2)))
    xa, ya = max(0, min(xa, w - 2)), max(0, min(ya, h - 2))
    xb, yb = max(xa + 1, min(xb, w)), max(ya + 1, min(yb, h))
    if corner == "tl":
        roi = card[ya:yb, xa:xb]
    elif corner == "tr":
        roi = card[ya:yb, w - xb:w - xa]
    elif corner == "bl":
        roi = card[h - yb:h - ya, xa:xb]
    elif corner == "br":
        roi = card[h - yb:h - ya, w - xb:w - xa]
    else:
        raise ValueError("corner must be one of tl, tr, bl, br")
    if rotate_180:
        roi = cv2.rotate(roi, cv2.ROTATE_180)
    if roi.size == 0:
        raise ValueError("empty corner ROI")
    return roi


def _to_gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _resize_pad(gray: np.ndarray, size: Tuple[int, int],
                pad_value: int = 255, interpolation: int = cv2.INTER_AREA) -> np.ndarray:
    """Resize preserving aspect ratio, then pad to the requested (w, h)."""
    target_w, target_h = size
    h, w = gray.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    resized = cv2.resize(gray, (new_w, new_h), interpolation=interp)
    canvas = np.full((target_h, target_w), pad_value, dtype=gray.dtype)
    x0 = (target_w - new_w) // 2
    y0 = (target_h - new_h) // 2
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def normalize_roi(roi: np.ndarray, size: Tuple[int, int] = (128, 128),
                  equalize: bool = True, clahe: bool = False,
                  pad_value: int = 255) -> np.ndarray:
    """Grayscale, aspect-preserving resize+pad, optional contrast enhancement."""
    gray = _to_gray(roi)
    gray = _resize_pad(gray, size, pad_value=pad_value)
    if clahe:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    elif equalize:
        gray = cv2.equalizeHist(gray)
    return gray


def normalize_card(card: np.ndarray, size: Tuple[int, int] = (64, 90),
                   equalize: bool = False, clahe: bool = False) -> np.ndarray:
    """Normalize a full rectified card to a fixed grayscale image."""
    gray = _to_gray(card)
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    if clahe:
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    elif equalize:
        gray = cv2.equalizeHist(gray)
    return gray


def normalize_card_color(card: np.ndarray, size: Tuple[int, int] = (64, 96)) -> np.ndarray:
    """Resize a rectified BGR card and return RGB uint8 (for the CNN)."""
    if card.ndim == 2:
        card = cv2.cvtColor(card, cv2.COLOR_GRAY2BGR)
    resized = cv2.resize(card, size, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)


# ------------------------------------------------------------------ previews
def make_preview(image: np.ndarray, label: str, score: float, output_path,
                 quad: Optional[np.ndarray] = None,
                 note: str = "") -> None:
    """Save a visual preview with an ASCII label banner (OpenCV cannot render CJK)."""
    preview = image.copy()
    if quad is not None:
        pts = np.asarray(quad, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(preview, [pts], True, (0, 255, 0), 3)
    banner_h = 46
    cv2.rectangle(preview, (0, 0), (preview.shape[1], banner_h), (25, 25, 25), -1)
    text = f"{label}  score={score:.3f}"
    if note:
        text += f"  {note}"
    cv2.putText(preview, text, (8, 31), cv2.FONT_HERSHEY_SIMPLEX,
                0.75, (255, 255, 255), 2, cv2.LINE_AA)
    save_image(output_path, preview)


def image_quality(image: np.ndarray) -> dict:
    """Cheap quality metrics used to flag blurred / overexposed inputs."""
    gray = _to_gray(image)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean())
    over = float((gray >= 250).mean())
    return {
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "laplacian_var": round(lap_var, 2),
        "mean_gray": round(mean, 2),
        "overexposed_ratio": round(over, 4),
        "blurry": lap_var < 40.0,
    }
