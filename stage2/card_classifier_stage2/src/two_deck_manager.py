# -*- coding: utf-8 -*-
"""Two-slot separation for two identical decks.

Physical provenance cannot be recovered from an unmarked mixed batch.  With
two decks every ordinary label appears twice; the practical rule is:
first confirmed copy -> SLOT A, second confirmed copy -> SLOT B, further
copies / rejected cards -> REVIEW.  If exactly two copies of every label exist,
slots A and B are two complete reconstructed decks.
"""

from __future__ import annotations

from collections import Counter

from .card_labels import JOKER_LABEL, ORDINARY_LABELS, is_joker_label
from .deck_manager import DeckManager


class TwoDeckSorter(DeckManager):
    def __init__(self, num_decks: int = 2, jokers_per_deck: int = 0):
        super().__init__(num_decks, jokers_per_deck)
        self.slot_counts = Counter({"A": 0, "B": 0, "REVIEW": 0})
        self.slot_by_label = {label: Counter() for label in ORDINARY_LABELS}
        self.slot_by_label[JOKER_LABEL] = Counter()

    def _slot_for(self, label: str) -> str:
        if label == JOKER_LABEL:
            if self.expected_jokers <= 0:
                return "REVIEW"
            return "A" if self.counts[label] <= self.jokers_per_deck else "B"
        return "A" if self.counts[label] <= 1 else "B"

    def add(self, label, meta=None):
        result = super().add(label, meta)
        normalized = str(result.get("label", "")).upper()
        if result["status"] == "ACCEPTED" and (
                normalized in ORDINARY_LABELS or is_joker_label(normalized)):
            slot = self._slot_for(normalized)
        else:
            slot = "REVIEW"
        self.slot_counts[slot] += 1
        if normalized in self.slot_by_label:
            self.slot_by_label[normalized][slot] += 1
        result["slot"] = slot
        return result

    def add_failure(self, reason: str = "image processing failed"):
        result = super().add_failure(reason)
        self.slot_counts["REVIEW"] += 1
        result["slot"] = "REVIEW"
        return result

    def correct(self, old_label: str, new_label: str):
        result = super().correct(old_label, new_label)
        if result.get("ok"):
            self._recompute_slots()
        return result

    def _recompute_slots(self):
        self.slot_counts = Counter({"A": 0, "B": 0, "REVIEW": 0})
        self.slot_by_label = {label: Counter() for label in ORDINARY_LABELS}
        self.slot_by_label[JOKER_LABEL] = Counter()
        for label in ORDINARY_LABELS:
            n = self.counts[label]
            a = min(n, 1)
            b = min(max(0, n - 1), max(0, self.num_decks - 1))
            self.slot_counts["A"] += a
            self.slot_counts["B"] += b
            self.slot_by_label[label]["A"] += a
            self.slot_by_label[label]["B"] += b
        j = self.counts[JOKER_LABEL]
        a = min(j, self.jokers_per_deck)
        b = min(max(0, j - self.jokers_per_deck), self.expected_jokers - a)
        self.slot_counts["A"] += a
        self.slot_counts["B"] += b
        self.slot_by_label[JOKER_LABEL]["A"] += a
        self.slot_by_label[JOKER_LABEL]["B"] += b
        self.slot_counts["REVIEW"] = (self.rejected + self.failed + self.duplicates)

    def snapshot(self):
        out = super().snapshot()
        expected_per_slot = (len(ORDINARY_LABELS) + self.jokers_per_deck
                             if self.num_decks == 2 else out["expected_count"])
        out["slots"] = {
            "A": self.slot_counts["A"], "B": self.slot_counts["B"],
            "REVIEW": self.slot_counts["REVIEW"],
            "expected_A": expected_per_slot if self.num_decks == 2 else out["expected_count"],
            "expected_B": expected_per_slot if self.num_decks == 2 else 0,
            "by_label": {k: dict(v) for k, v in self.slot_by_label.items() if v},
        }
        out["slot_rule"] = "first copy -> A; second copy -> B; extra/UNKNOWN -> REVIEW"
        return out
