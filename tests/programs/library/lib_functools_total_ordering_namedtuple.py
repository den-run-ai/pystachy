# functools.total_ordering of a NamedTuple: tuple's four ordering methods are the class's too,
# so CPython's decorator adds none, and only the method the class defines replaces tuple's.
from functools import total_ordering
from typing import NamedTuple


@total_ordering
class Card(NamedTuple):
    rank: int
    suit: str

    def __lt__(self, other: "Card") -> bool:
        return (self.suit, self.rank) < (other.suit, other.rank)


@total_ordering
class Point(NamedTuple):
    # (no ordering method of its own: tuple's are the roots)
    x: int
    y: int


def table(a, b) -> list[bool]:
    return [a < b, a <= b, a > b, a >= b, b < a, b <= a, b > a, b >= a]


a, b = Card(2, "spades"), Card(10, "hearts")
print(table(a, b), table(a, a))
print(sorted([a, b, Card(5, "clubs")]), min(a, b), max(a, b))
p, q = Point(1, 5), Point(2, 0)
print(table(p, q), sorted([q, p]), max(p, q))
