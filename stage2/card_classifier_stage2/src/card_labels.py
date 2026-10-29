# -*- coding: utf-8 -*-
"""Canonical 52-class label system.

Label = rank + suit, e.g. AS, 10H, KC.
Ranks use T-less notation: A,2,...,10,J,Q,K.
Suits: S (spades), H (hearts), D (diamonds), C (clubs).
"""

from __future__ import annotations

from typing import Tuple

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]

# Suit-major order, kept identical to the original project to avoid breaking
# previously saved models / filenames: AS..KS, AH..KH, AD..KD, AC..KC.
LABELS = [rank + suit for suit in SUITS for rank in RANKS]
LABEL_TO_INDEX = {label: i for i, label in enumerate(LABELS)}
INDEX_TO_LABEL = {i: label for label, i in LABEL_TO_INDEX.items()}

# JOKER is a batch label, not a trained visual class: there is no Joker training
# data in this project, so classifiers never output it.  The UI/batch layer may
# add it manually (or via an explicitly-marked simulated event).
ORDINARY_LABELS = LABELS
JOKER_LABEL = "JOKER"
JOKER_ALIASES = {
    "JK", "JR", "JB", "JOKER1", "JOKER2", "JOKER_RED", "JOKER_BLACK",
    "REDJOKER", "BLACKJOKER", "RED_JOKER", "BLACK_JOKER", "JOKER",
}

if len(LABELS) != 52 or len(set(LABELS)) != 52:
    raise RuntimeError("internal label table is broken: expected 52 unique labels")


def is_valid_label(label: str) -> bool:
    return isinstance(label, str) and label.upper() in LABEL_TO_INDEX


def is_joker_label(label: str) -> bool:
    return str(label).strip().upper().replace("-", "").replace(" ", "") in JOKER_ALIASES


def normalize_batch_label(label: str) -> str:
    """Normalize a batch label: 52 ordinary labels or JOKER aliases."""
    raw = str(label).strip().upper().replace("-", "").replace(" ", "")
    if raw in LABEL_TO_INDEX:
        return raw
    if raw in JOKER_ALIASES:
        return JOKER_LABEL
    raise ValueError(f"unknown batch label: {label!r}")


def normalize_label(label: str) -> str:
    label = str(label).strip().upper()
    if label not in LABEL_TO_INDEX:
        raise ValueError(f"unknown card label: {label!r}")
    return label


def label_to_index(label: str) -> int:
    return LABEL_TO_INDEX[normalize_label(label)]


def index_to_label(index: int) -> str:
    try:
        return INDEX_TO_LABEL[int(index)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid class index: {index!r}") from exc


def parse_label(label: str) -> Tuple[str, str]:
    """Return (rank, suit) for a valid label."""
    label = normalize_label(label)
    if label.startswith("10"):
        return "10", label[2]
    return label[0], label[1]


def make_label(rank: str, suit: str) -> str:
    rank, suit = str(rank).strip().upper(), str(suit).strip().upper()
    label = rank + suit
    return normalize_label(label)


def label_from_filename(path) -> str:
    """Read a label from a filename prefix such as ``10H_test_01.jpg``.

    The prefix must be a valid 52-class label.  This intentionally raises on
    unknown prefixes instead of silently counting them as wrong predictions.
    """
    from pathlib import Path

    stem = Path(path).stem.strip()
    prefix = stem.split("_")[0].upper()
    if not is_valid_label(prefix):
        raise ValueError(f"filename does not start with a valid label: {Path(path).name}")
    return prefix
