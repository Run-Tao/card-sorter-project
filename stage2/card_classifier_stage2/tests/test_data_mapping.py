# -*- coding: utf-8 -*-
"""Tests for dataset label mapping used by prepare_data.py."""

import unittest

from prepare_data import french_folder_to_label
from src.card_labels import LABELS


class TestFrenchMapping(unittest.TestCase):
    def test_ranks_and_suits(self):
        self.assertEqual(french_folder_to_label("Coeur 1"), "AH")
        self.assertEqual(french_folder_to_label("Coeur 10"), "10H")
        self.assertEqual(french_folder_to_label("Carreau Dame"), "QD")
        self.assertEqual(french_folder_to_label("Pique Roi"), "KS")
        self.assertEqual(french_folder_to_label("Trefle Valet"), "JC")

    def test_all_folders_map_into_52(self):
        suits = ["Coeur", "Carreau", "Pique", "Trefle"]
        ranks = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Valet", "Dame", "Roi"]
        got = {french_folder_to_label(f"{s} {r}") for s in suits for r in ranks}
        self.assertEqual(got, set(LABELS))

    def test_bad_folder(self):
        with self.assertRaises(ValueError):
            french_folder_to_label("Unknown 1")


if __name__ == "__main__":
    unittest.main()
