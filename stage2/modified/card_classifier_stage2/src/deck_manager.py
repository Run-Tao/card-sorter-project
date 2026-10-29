from collections import Counter
from .card_labels import ORDINARY_LABELS, JOKER_LABEL, normalize_label


class DeckManager:
    """Track a multi-deck batch (default: two 54-card decks = 108 cards).

    For the course task's 104-card variant (two decks without jokers), use
    ``DeckManager(num_decks=2, jokers_per_deck=0)``.

    UNKNOWN/REJECT predictions are unresolved and do not count as missing until
    the batch is finalized with no unresolved cards remaining.
    """

    def __init__(self, num_decks: int = 2, jokers_per_deck: int = 2):
        if num_decks < 1:
            raise ValueError("num_decks must be >= 1")
        if jokers_per_deck < 0:
            raise ValueError("jokers_per_deck must be >= 0")
        self.num_decks = int(num_decks)
        self.jokers_per_deck = int(jokers_per_deck)
        self.expected_jokers = self.num_decks * self.jokers_per_deck
        self.counts = Counter()
        self.unresolved = 0
        self.duplicates = []
        self.accepted = []

    @property
    def expected_count(self) -> int:
        return len(ORDINARY_LABELS) * self.num_decks + self.expected_jokers

    def add(self, label):
        label = normalize_label(label)
        if label in {"UNKNOWN", "REJECT", ""}:
            self.unresolved += 1
            return {"status": "UNRESOLVED", "label": label or "UNKNOWN"}
        if label not in ORDINARY_LABELS and label != JOKER_LABEL:
            self.unresolved += 1
            return {"status": "INVALID_LABEL", "label": label}
        if label == JOKER_LABEL:
            limit = self.expected_jokers
            if limit == 0:
                self.unresolved += 1
                return {"status": "INVALID_LABEL", "label": label}
        else:
            limit = self.num_decks
        if self.counts[label] >= limit:
            item = {"status": "DUPLICATE", "label": label}
            self.duplicates.append(item)
            return item
        self.counts[label] += 1
        self.accepted.append(label)
        return {"status": "ACCEPTED", "label": label}

    def finalize(self):
        missing_counts = {
            label: self.num_decks - self.counts[label]
            for label in ORDINARY_LABELS
            if self.counts[label] < self.num_decks
        }
        missing = list(missing_counts)
        joker_missing = max(0, self.expected_jokers - self.counts[JOKER_LABEL])
        if self.unresolved:
            status = "INCOMPLETE_UNRESOLVED"
        elif self.duplicates:
            status = "DUPLICATES_FOUND"
        elif missing or joker_missing:
            status = "MISSING_CARDS"
        else:
            status = f"COMPLETE_{self.expected_count}"
        return {
            "status": status,
            "expected_count": self.expected_count,
            "accepted_count": len(self.accepted),
            "ordinary_count": sum(self.counts[x] for x in ORDINARY_LABELS),
            "joker_count": self.counts[JOKER_LABEL],
            "missing_ordinary": missing,
            "missing_counts": missing_counts,
            "missing_jokers": joker_missing,
            "unresolved_count": self.unresolved,
            "duplicates": list(self.duplicates),
        }
