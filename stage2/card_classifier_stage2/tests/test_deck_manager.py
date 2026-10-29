# -*- coding: utf-8 -*-
"""Tests for two-deck / Joker batch bookkeeping."""

import unittest

from src.card_labels import JOKER_LABEL, LABELS, normalize_batch_label
from src.deck_manager import DeckManager


def fill(manager, copies):
    for _ in range(copies):
        for label in LABELS:
            manager.add(label)


class TestDeckManager(unittest.TestCase):
    def test_two_decks_104(self):
        m = DeckManager(2, 0)
        fill(m, 2)
        s = m.snapshot()
        self.assertEqual(s["status"], "COMPLETE_104")
        self.assertEqual(s["accepted"], 104)
        self.assertEqual(s["expected_count"], 104)

    def test_two_decks_108_with_jokers(self):
        m = DeckManager(2, 2)
        fill(m, 2)
        for _ in range(4):
            self.assertEqual(m.add(JOKER_LABEL)["status"], "ACCEPTED")
        self.assertEqual(m.snapshot()["status"], "COMPLETE_108")

    def test_single_deck_54(self):
        m = DeckManager(1, 2)
        fill(m, 1)
        m.add(JOKER_LABEL); m.add(JOKER_LABEL)
        self.assertEqual(m.snapshot()["status"], "COMPLETE_54")

    def test_second_copy_is_normal_third_is_duplicate(self):
        m = DeckManager(2, 0)
        self.assertEqual(m.add("AS")["status"], "ACCEPTED")
        self.assertEqual(m.add("AS")["status"], "ACCEPTED")
        self.assertEqual(m.add("AS")["status"], "DUPLICATE")
        s = m.snapshot()
        self.assertEqual(s["duplicates"], 1)
        self.assertEqual(s["status"], "DUPLICATES_FOUND")

    def test_unresolved_prevents_missing_claim(self):
        m = DeckManager(2, 0)
        m.add("UNKNOWN")
        s = m.snapshot()
        self.assertEqual(s["status"], "INCOMPLETE_UNRESOLVED")
        self.assertTrue(s["missing_provisional"])

    def test_joker_not_allowed_in_104(self):
        m = DeckManager(2, 0)
        self.assertEqual(m.add(JOKER_LABEL)["status"], "INVALID_LABEL")

    def test_joker_aliases(self):
        for raw in ("JR", "JK", "JOKER_RED", "JOKER_BLACK", "RED_JOKER", "JOKER"):
            self.assertEqual(normalize_batch_label(raw), JOKER_LABEL)

    def test_failure_is_counted(self):
        m = DeckManager(2, 0)
        m.add_failure("decode")
        s = m.snapshot()
        self.assertEqual(s["failed"], 1)
        self.assertEqual(s["status"], "INCOMPLETE_UNRESOLVED")

    def test_progress_and_missing(self):
        m = DeckManager(2, 0)
        m.add("AS")
        s = m.snapshot()
        self.assertAlmostEqual(s["progress"], 1/104)
        self.assertEqual(s["missing"]["AS"], 1)

    def test_human_correction_keeps_processed(self):
        m = DeckManager(2, 0)
        m.add("AS")
        m.add("AS")
        m.add("7S")
        before = m.snapshot()["processed"]
        res = m.correct("AS", "7S")
        self.assertTrue(res["ok"])
        s = m.snapshot()
        self.assertEqual(s["processed"], before)
        self.assertEqual(s["counts"]["AS"], 1)
        self.assertEqual(s["counts"]["7S"], 2)
        self.assertEqual(s["accepted"], 3)

    def test_human_correction_capacity_rolls_back(self):
        m = DeckManager(1, 0)
        m.add("AS")
        m.add("7S")
        res = m.correct("7S", "AS")
        self.assertFalse(res["ok"])
        s = m.snapshot()
        self.assertEqual(s["counts"]["AS"], 1)
        self.assertEqual(s["counts"]["7S"], 1)


if __name__ == "__main__":
    unittest.main()
