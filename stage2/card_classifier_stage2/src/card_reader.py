# -*- coding: utf-8 -*-
"""Full card reader: localization + rank head + suit head.

This is deliberately two semantic heads (13 rank, 4 suit), not a 52-class
softmax.  Registered user samples take precedence; otherwise the rank OCR head
and suit head are combined and either can force a review.
"""

from __future__ import annotations

from pathlib import Path

from .corner_semantic import CornerSemanticReader
from .suit_reader import SuitReader, SUIT_NAME

RANKS = {"A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"}


class CardReader:
    name = "card"

    def __init__(self):
        self.suit_reader = SuitReader()
        self.corner = CornerSemanticReader()

    def predict(self, image) -> dict:
        base = self.suit_reader.predict(image)
        rank_r = self.corner.predict(image)
        rank = str(rank_r.get("rank") or "").strip().upper()
        rank_conf = float(rank_r.get("rank_conf") or 0.0)
        suit = base.get("suit") or ""
        suit_conf = float(base.get("score") or 0.0)
        valid_rank = rank in RANKS
        label = rank + suit if (valid_rank and suit) else ""
        accepted = bool(label and rank_conf >= 0.35 and suit_conf >= 0.45)
        return {
            **base,
            "rank": rank,
            "rank_conf": rank_conf,
            "suit": suit,
            "suit_conf": suit_conf,
            "suit_name": SUIT_NAME.get(suit, ""),
            "label": label if accepted else "UNKNOWN",
            "best_label": label,
            "score": (rank_conf + suit_conf) / 2.0 if label else 0.0,
            "top5": [[label, (rank_conf + suit_conf) / 2.0]] if label else [],
            "accepted": accepted,
            "method": "card_rank_suit",
        }
