# -*- coding: utf-8 -*-
"""Corner-semantic reader: OCR the rank and classify the suit symbol.

This is the cross-design path: it does not compare the whole card with a
52-class template bank.  It rectifies the card, tries four orientations, reads
the small corner rank with EasyOCR and classifies the suit symbol with a
font-template + colour bank.  Works on standard poker cards and non-standard
cards that keep a conventional rank/suit index (e.g. Sanguosha cards).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .card_labels import is_valid_label

SUIT_SYMBOL = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
FONTS = ["seguisym.ttf", "arial.ttf", "times.ttf", "georgia.ttf", "segoeui.ttf"]
OCR_ALLOW = "A23456789JQK10"
RANK_ALIASES = {"1": "A"}


def _binarize(gray: np.ndarray, size=(64, 64)) -> Optional[np.ndarray]:
    _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ys, xs = np.where(b > 0)
    if len(xs) < 10:
        return None
    b = b[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(b, size, interpolation=cv2.INTER_NEAREST)


class CornerSemanticReader:
    name = "corner"

    def __init__(self, threshold: float = 0.40, lazy_ocr: bool = True):
        self.threshold = float(threshold)
        self._reader = None
        self._templates = self._load_suit_templates()
        self._lazy = lazy_ocr

    # ------------------------------------------------------------------ OCR
    @property
    def reader(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return self._reader

    def _ocr_rank(self, crop_bgr: np.ndarray) -> Tuple[str, float]:
        if crop_bgr is None or crop_bgr.size == 0:
            return "", 0.0
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
        _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        b = cv2.copyMakeBorder(b, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
        try:
            out = self.reader.recognize(b, detail=1, allowlist=OCR_ALLOW)
        except Exception:
            return "", 0.0
        best_text, best_conf = "", 0.0
        for _, text, conf in out:
            text = str(text).strip().upper()
            text = RANK_ALIASES.get(text, text)
            if text in {"A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"}:
                if conf > best_conf:
                    best_text, best_conf = text, float(conf)
        return best_text, best_conf

    # --------------------------------------------------------------- suit
    def _load_suit_templates(self) -> List[dict]:
        out = []
        for suit, symbol in SUIT_SYMBOL.items():
            for fn in FONTS:
                try:
                    font = ImageFont.truetype(str(Path("C:/Windows/Fonts") / fn), 80)
                except Exception:
                    continue
                img = Image.new("L", (120, 120), 255)
                ImageDraw.Draw(img).text((10, 0), symbol, font=font, fill=0)
                b = _binarize(np.array(img))
                if b is not None:
                    out.append({"suit": suit, "mask": b})
        return out

    def _suit(self, card: np.ndarray, win, rotation: int) -> Tuple[str, float]:
        h, w = card.shape[:2]
        # Template-scan a slightly larger corner; this is more robust than
        # picking the largest connected component (which is often the border).
        roi = card[0:int(h * 0.36), 0:int(w * 0.30)]
        if roi.size == 0:
            return "", 0.0
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, q = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        scored = []
        for t in self._templates:
            mask = t["mask"]
            for scale in (0.20, 0.28, 0.38, 0.50, 0.65, 0.80):
                m = cv2.resize(mask, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_NEAREST)
                if m.shape[0] >= q.shape[0] or m.shape[1] >= q.shape[1]:
                    continue
                res = cv2.matchTemplate(q, m, cv2.TM_CCOEFF_NORMED)
                _, mx, _, loc = cv2.minMaxLoc(res)
                scored.append((float(mx), t["suit"], loc[0], loc[1], m.shape[1], m.shape[0]))
        if not scored:
            return "", 0.0
        scored.sort(reverse=True)
        # colour tie-break from the matched patch
        def red_at(item):
            _, _, x, y, ww, hh = item
            patch = roi[int(y / 3):int((y + hh) / 3), int(x / 3):int((x + ww) / 3)]
            if patch.size == 0:
                return False
            b, g, r = [float(v) for v in patch.reshape(-1, 3).mean(axis=0)]
            return r > b + 30
        best = scored[0]
        if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.03:
            fam = {"H", "D"} if red_at(best) else {"S", "C"}
            alt = next((s for s in scored if s[1] in fam), best)
            best = alt
        return best[1], best[0]

    # -------------------------------------------------------------- predict
    def _original_rank(self, image: np.ndarray):
        h, w = image.shape[:2]
        # Absolute top-left windows (fractions of the full image).  Close-up
        # cards in the demo all have the index in the top-left corner.
        windows = [(0.02, 0.02, 0.16, 0.18), (0.03, 0.03, 0.15, 0.17),
                   (0.02, 0.03, 0.15, 0.20), (0.02, 0.02, 0.18, 0.20),
                   (0.03, 0.03, 0.21, 0.21)]
        best = None
        for x1, y1, x2, y2 in windows:
            crop = image[int(h * y1):int(h * y2), int(w * x1):int(w * x2)]
            rank, conf = self._ocr_rank(crop)
            if rank and (best is None or conf > best[1]):
                best = (rank, conf, crop)
        if best is None:
            return None
        rank, conf, crop = best
        suit, sconf = self._suit_from_original(image)
        if not suit:
            b, g, r = [float(v) for v in crop.reshape(-1, 3).mean(axis=0)]
            suit = "H" if r > b + 25 else "S"
            sconf = 0.3
        return {"label": rank + suit, "best_label": rank + suit,
                "score": float(conf), "rank": rank, "suit": suit,
                "rank_conf": float(conf), "suit_conf": float(sconf), "semantic": True,
                "detected": False, "quad": None,
                "top5": [[rank + suit, float(conf)]], "corner": "tl",
                "rotation": 0, "method": "corner_semantic_original"}

    def _suit_from_original(self, image: np.ndarray):
        h, w = image.shape[:2]
        # Close-up standard cards: suit symbol sits just below the top-left rank.
        crop = image[int(h * 0.12):int(h * 0.32), int(w * 0.02):int(w * 0.20)]
        if crop.size == 0:
            return "", 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        if n < 2:
            return "", 0.0
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, bw, bh, area = stats[idx]
        if area < 30:
            return "", 0.0
        q = cv2.resize(mask[y:y + bh, x:x + bw], (64, 64), interpolation=cv2.INTER_NEAREST)
        best_suit, best_score = "", 0.0
        for t in self._templates:
            a, b = q > 0, t["mask"] > 0
            iou = np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum())
            if iou > best_score:
                best_suit, best_score = t["suit"], float(iou)
        return best_suit, best_score

    def predict(self, image) -> Dict:
        from .image_utils import read_image, rectify_card

        if isinstance(image, (str, Path)):
            arr = read_image(image)
        else:
            arr = image
        if arr.shape[1] == 210 and arr.shape[0] == 294:
            card, info = arr, {"detected": True, "quad": None, "method": "already_canonical"}
        else:
            card, info = rectify_card(arr)
        # Close-up photos often fail quad detection; OCR original TL directly.
        # Prefer original tight windows when confidence is high, even if a
        # full-frame/quad localization succeeded (the warp can shift glyphs).
        original = self._original_rank(arr)
        if original is not None and original.get("rank_conf", 0.0) >= 0.50:
            return original
        if not info.get("detected") and original is not None:
            return original
        best = None
        h, w = card.shape[:2]
        # A successful rectification normally has the index in the TL corner.
        regions = [("tl", 0.0, 0.0, 0.36, 0.38)]
        local_windows = [
            (0.0, 0.02, 0.50, 0.42),
            (0.04, 0.02, 0.48, 0.40),
            (0.08, 0.00, 0.42, 0.36),
            (0.02, 0.00, 0.55, 0.50),
        ]
        for rot in range(4):
            c = card
            for _ in range(rot):
                c = cv2.rotate(c, cv2.ROTATE_90_CLOCKWISE)
            for cname, rx1, ry1, rx2, ry2 in regions:
                sub = c[int(h * ry1):int(h * ry2), int(w * rx1):int(w * rx2)]
                sh, sw = sub.shape[:2]
                for lx, ly, lw, lh in local_windows:
                    crop = sub[int(sh * ly):int(sh * (ly + lh)),
                               int(sw * lx):int(sw * (lx + lw))]
                    rank, conf = self._ocr_rank(crop)
                    if not rank:
                        continue
                    score = float(conf)
                    if best is None or score > best["score"]:
                        best = {"label": rank, "rank": rank, "suit": "",
                                "score": score, "rank_conf": float(conf),
                                "suit_conf": 0.0, "rotation": rot,
                                "corner": cname}
        if best is None:
            return {"label": "UNKNOWN", "best_label": "UNKNOWN", "score": 0.0,
                    "rank": "", "suit": "", "rank_conf": 0.0, "suit_conf": 0.0,
                    "semantic": True, "detected": info.get("detected", False),
                    "quad": info.get("quad"), "top5": [], "corner": "tl",
                    "method": "corner_semantic_failed"}
        rank = best["rank"]
        return {
            "label": rank, "best_label": rank, "score": best["score"],
            "rank": rank, "suit": "", "rank_conf": best["rank_conf"],
            "suit_conf": 0.0, "semantic": True,
            "detected": bool(info.get("detected")), "quad": info.get("quad"),
            "top5": [[rank, round(best["score"], 4)]],
            "corner": best["corner"], "rotation": best["rotation"],
            "method": "corner_semantic_rank",
        }
