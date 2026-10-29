import unittest
from src.deck_manager import DeckManager
from src.card_labels import ORDINARY_LABELS, JOKER_LABEL, normalize_label


class DeckManagerTests(unittest.TestCase):
    def test_complete_two_decks_108(self):
        manager = DeckManager()
        for _ in range(2):
            for label in ORDINARY_LABELS:
                self.assertEqual(manager.add(label)["status"], "ACCEPTED")
        for _ in range(4):
            manager.add(JOKER_LABEL)
        result = manager.finalize()
        self.assertEqual(result["status"], "COMPLETE_108")
        self.assertEqual(result["accepted_count"], 108)

    def test_complete_104_without_jokers(self):
        manager = DeckManager(num_decks=2, jokers_per_deck=0)
        for _ in range(2):
            for label in ORDINARY_LABELS:
                manager.add(label)
        self.assertEqual(manager.finalize()["status"], "COMPLETE_104")
        self.assertEqual(manager.expected_count, 104)

    def test_one_deck_legacy_54(self):
        manager = DeckManager(num_decks=1, jokers_per_deck=2)
        for label in ORDINARY_LABELS:
            manager.add(label)
        manager.add(JOKER_LABEL)
        manager.add(JOKER_LABEL)
        self.assertEqual(manager.finalize()["status"], "COMPLETE_54")

    def test_third_copy_is_duplicate_in_two_decks(self):
        manager = DeckManager()
        self.assertEqual(manager.add("AS")["status"], "ACCEPTED")
        self.assertEqual(manager.add("AS")["status"], "ACCEPTED")
        self.assertEqual(manager.add("AS")["status"], "DUPLICATE")
        self.assertEqual(manager.finalize()["status"], "DUPLICATES_FOUND")

    def test_unknown_prevents_missing_claim(self):
        manager = DeckManager()
        manager.add("UNKNOWN")
        result = manager.finalize()
        self.assertEqual(result["status"], "INCOMPLETE_UNRESOLVED")
        self.assertGreater(result["unresolved_count"], 0)

    def test_joker_aliases(self):
        for raw in ("JR", "JK", "JOKER_RED", "JOKER_BLACK", "REDJOKER"):
            self.assertEqual(normalize_label(raw), JOKER_LABEL)
        self.assertEqual(normalize_label("JOKER"), JOKER_LABEL)

    def test_joker_limit(self):
        manager = DeckManager()
        for _ in range(4):
            self.assertEqual(manager.add(JOKER_LABEL)["status"], "ACCEPTED")
        self.assertEqual(manager.add(JOKER_LABEL)["status"], "DUPLICATE")


if __name__ == "__main__":
    unittest.main()
