# -*- coding: utf-8 -*-
"""Two-deck slot separation and ensemble feature tests."""

import unittest

from src.card_labels import JOKER_LABEL, LABELS
from src.ensemble import FEATURE_NAMES, _ticket, candidates_for
from src.two_deck_manager import TwoDeckSorter


class TestTwoDeckSorter(unittest.TestCase):
    def test_first_copy_a_second_b_third_review(self):
        s = TwoDeckSorter(2, 0)
        self.assertEqual(s.add("AS")["slot"], "A")
        self.assertEqual(s.add("AS")["slot"], "B")
        self.assertEqual(s.add("AS")["slot"], "REVIEW")
        snap = s.snapshot()
        self.assertEqual(snap["slots"]["A"], 1)
        self.assertEqual(snap["slots"]["B"], 1)
        self.assertEqual(snap["slots"]["REVIEW"], 1)

    def test_complete_two_decks_has_two_complete_slots(self):
        s = TwoDeckSorter(2, 0)
        for _ in range(2):
            for label in LABELS:
                s.add(label)
        snap = s.snapshot()
        self.assertEqual(snap["status"], "COMPLETE_104")
        self.assertEqual(snap["slots"]["A"], 52)
        self.assertEqual(snap["slots"]["B"], 52)
        self.assertEqual(snap["slots"]["REVIEW"], 0)

    def test_jokers_split_across_slots(self):
        s = TwoDeckSorter(2, 2)
        for _ in range(2):
            for label in LABELS:
                s.add(label)
        for _ in range(4):
            s.add(JOKER_LABEL)
        snap = s.snapshot()
        self.assertEqual(snap["status"], "COMPLETE_108")
        self.assertEqual(snap["slots"]["A"], 54)
        self.assertEqual(snap["slots"]["B"], 54)

    def test_unknown_is_review(self):
        s = TwoDeckSorter(2, 0)
        res = s.add("UNKNOWN")
        self.assertEqual(res["slot"], "REVIEW")
        self.assertEqual(s.snapshot()["slots"]["REVIEW"], 1)


class TestEnsembleFeatures(unittest.TestCase):
    def test_candidate_and_ticket_shape(self):
        def r(label, score):
            return {"best_label": label, "score": score, "margin": 0.2, "detected": True,
                    "top5": [[label, score], ["KC", 0.1]], "corner": ""}
        results = {"template": r("AS", 0.4), "hog_svm": r("AS", 0.9), "cnn": r("KC", 0.6)}
        cands = candidates_for(results)
        self.assertEqual(cands, ["AS", "KC"])
        row = _ticket("AS", results, {"blurry": False, "laplacian_var": 100})
        self.assertEqual(len(row), len(FEATURE_NAMES))


if __name__ == "__main__":
    unittest.main()
