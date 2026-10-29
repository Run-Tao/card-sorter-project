# -*- coding: utf-8 -*-
"""Deck / batch bookkeeping for one or more standard decks.

Visual classes are the 52 ordinary labels (the trained classifier cannot output
JOKER because no Joker training data is available).  JOKER is a *batch* label:
it can be added manually or through an explicitly-marked simulated event, so the
expected number of physical Jokers is still configurable.

Rules:
- every ordinary label has capacity ``num_decks`` (two copies are normal for two
  decks, not an error);
- Joker capacity is ``num_decks * jokers_per_deck``;
- a rejected/failed card is unresolved and prevents a "complete" verdict;
- missing labels are only a final verdict when there are no unresolved cards.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Optional

from .card_labels import (JOKER_LABEL, ORDINARY_LABELS, is_joker_label,
                          normalize_batch_label)


class DeckManager:
    def __init__(self, num_decks: int = 2, jokers_per_deck: int = 0):
        if num_decks < 1:
            raise ValueError("num_decks must be >= 1")
        if jokers_per_deck < 0:
            raise ValueError("jokers_per_deck must be >= 0")
        self.num_decks = int(num_decks)
        self.jokers_per_deck = int(jokers_per_deck)
        self.expected_jokers = self.num_decks * self.jokers_per_deck
        self.expected_count = len(ORDINARY_LABELS) * self.num_decks + self.expected_jokers
        self.counts = Counter()
        self.processed = 0
        self.accepted = 0
        self.rejected = 0
        self.failed = 0
        self.duplicates = 0
        self.duplicate_labels = Counter()
        self.accepted_labels = []

    # ------------------------------------------------------------------ add
    def add(self, label: str, meta: Optional[dict] = None) -> Dict:
        """Add one recognition result.  Returns a small status record."""
        raw = str(label).strip().upper()
        self.processed += 1
        if raw in {"", "UNKNOWN", "REJECT", "待确认"}:
            self.rejected += 1
            return {"status": "REJECTED", "label": "UNKNOWN",
                    "reason": (meta or {}).get("reason", "low confidence")}
        try:
            label = normalize_batch_label(raw)
        except ValueError:
            self.failed += 1
            return {"status": "INVALID_LABEL", "label": raw}
        if is_joker_label(label):
            if self.expected_jokers <= 0:
                self.failed += 1
                return {"status": "INVALID_LABEL", "label": label,
                        "reason": "batch is configured without Jokers"}
            limit = self.expected_jokers
        else:
            limit = self.num_decks
        if self.counts[label] >= limit:
            self.duplicates += 1
            self.duplicate_labels[label] += 1
            return {"status": "DUPLICATE", "label": label}
        self.counts[label] += 1
        self.accepted += 1
        self.accepted_labels.append(label)
        return {"status": "ACCEPTED", "label": label}

    def add_failure(self, reason: str = "image processing failed") -> Dict:
        self.processed += 1
        self.failed += 1
        return {"status": "FAILED", "label": "FAILED", "reason": reason}

    # ------------------------------------------------------------- reporting
    @property
    def unresolved(self) -> int:
        return self.rejected + self.failed

    def missing(self) -> Dict[str, int]:
        return {label: self.num_decks - self.counts[label]
                for label in ORDINARY_LABELS
                if self.counts[label] < self.num_decks}

    def status(self) -> str:
        if self.duplicates:
            return "DUPLICATES_FOUND"
        if self.unresolved:
            return "INCOMPLETE_UNRESOLVED"
        if self.processed < self.expected_count:
            return "IN_PROGRESS"
        if self.accepted < self.expected_count or self.missing():
            return "MISSING_CARDS"
        return f"COMPLETE_{self.expected_count}"

    def snapshot(self) -> Dict:
        missing = self.missing()
        status = self.status()
        return {
            "num_decks": self.num_decks,
            "jokers_per_deck": self.jokers_per_deck,
            "expected_count": self.expected_count,
            "expected_per_label": self.num_decks,
            "expected_jokers": self.expected_jokers,
            "processed": self.processed,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "failed": self.failed,
            "unresolved": self.unresolved,
            "duplicates": self.duplicates,
            "duplicate_labels": dict(self.duplicate_labels),
            "pending": max(0, self.expected_count - self.processed),
            "progress": min(1.0, self.processed / self.expected_count)
            if self.expected_count else 0.0,
            "status": status,
            "complete": status.startswith("COMPLETE_"),
            "counts": {label: int(self.counts[label]) for label in ORDINARY_LABELS},
            "joker_count": int(self.counts[JOKER_LABEL]),
            "missing": missing,
            "missing_count": sum(missing.values()),
            "missing_provisional": bool(self.unresolved and missing),
        }

    def reset(self):
        self.__init__(self.num_decks, self.jokers_per_deck)

    def correct(self, old_label: str, new_label: str) -> Dict:
        """Apply a human label correction without changing ``processed``.

        Returns ``{ok: bool, reason: str}``.  On capacity failure the original
        count is restored, so the batch state never silently changes.
        """
        old = str(old_label).strip().upper()
        new = str(new_label).strip().upper()
        if old == new:
            return {"ok": True, "reason": "unchanged"}
        # remove old contribution
        if old in {"UNKNOWN", "REJECT", ""}:
            if self.rejected <= 0:
                return {"ok": False, "reason": "no rejected record to correct"}
            self.rejected -= 1
        elif old == "FAILED":
            if self.failed <= 0:
                return {"ok": False, "reason": "no failed record to correct"}
            self.failed -= 1
        else:
            try:
                old = normalize_batch_label(old)
            except ValueError:
                return {"ok": False, "reason": f"invalid old label: {old}"}
            if self.counts[old] <= 0:
                return {"ok": False, "reason": f"label {old} not present"}
            self.counts[old] -= 1
            self.accepted -= 1
            if old in self.accepted_labels:
                self.accepted_labels.remove(old)
        # add new contribution
        if new in {"UNKNOWN", "REJECT", ""}:
            self.rejected += 1
            return {"ok": True, "reason": "corrected to UNKNOWN"}
        try:
            new = normalize_batch_label(new)
        except ValueError:
            # rollback old
            self._restore(old)
            return {"ok": False, "reason": f"invalid new label: {new}"}
        limit = self.expected_jokers if is_joker_label(new) else self.num_decks
        if (is_joker_label(new) and self.expected_jokers <= 0) or self.counts[new] >= limit:
            self._restore(old)
            return {"ok": False, "reason": f"capacity reached for {new}"}
        self.counts[new] += 1
        self.accepted += 1
        self.accepted_labels.append(new)
        return {"ok": True, "reason": "corrected"}

    def _restore(self, old: str):
        if old in {"UNKNOWN", "REJECT", ""}:
            self.rejected += 1
        elif old == "FAILED":
            self.failed += 1
        else:
            self.counts[old] += 1
            self.accepted += 1
            self.accepted_labels.append(old)
