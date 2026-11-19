# Classes for tests/programs/library/lib_pprint_mixed_keys_module.py, in a module whose name makes
# the type of a Card, "<class 'Cards.Card'>", sort before "<class 'NoneType'>", and that of a Suit,
# an enum class's "<enum 'Suit'>", after it.
from enum import Enum


class Suit(Enum):
    HEARTS = 1
    SPADES = 2


class Card:
    def __init__(self, rank: int) -> None:
        self.rank = rank

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank < other.rank

    def __repr__(self) -> str:
        return "Card(%d)" % self.rank
