RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]

# 52 ordinary-card identities plus one visual JOKER class.
# The batch manager expects exactly two physical jokers, without requiring
# the two joker designs to be visually distinguishable.
ORDINARY_LABELS = [rank + suit for suit in SUITS for rank in RANKS]
JOKER_LABEL = "JOKER"
LABELS = ORDINARY_LABELS + [JOKER_LABEL]

ALIASES = {
    "JK": JOKER_LABEL,
    "JR": JOKER_LABEL,
    "JB": JOKER_LABEL,
    "JOKER1": JOKER_LABEL,
    "JOKER2": JOKER_LABEL,
    "JOKER_RED": JOKER_LABEL,
    "JOKER_BLACK": JOKER_LABEL,
    "REDJOKER": JOKER_LABEL,
    "BLACKJOKER": JOKER_LABEL,
    "RED_JOKER": JOKER_LABEL,
    "BLACK_JOKER": JOKER_LABEL,
}

def normalize_label(label: str) -> str:
    label = str(label).strip().upper().replace("-", "").replace(" ", "")
    return ALIASES.get(label, label)

def is_valid_label(label: str) -> bool:
    return normalize_label(label) in LABELS
