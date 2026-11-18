# functools.total_ordering of subclasses whose bases already have all four ordering methods:
# a base the decorator completed, and a dataclass with order=True. CPython's decorator adds
# none to the subclass, so only the method its body defines replaces the inherited one.
from dataclasses import dataclass
from functools import total_ordering


@total_ordering
class Word:
    def __init__(self, s: str) -> None:
        self.s = s

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Word) and self.s == other.s

    def __lt__(self, other: "Word") -> bool:
        print("Word.__lt__")
        return self.s < other.s


@total_ordering
class ShortFirst(Word):
    # its <= orders by length first; <, > and >= stay Word's (__lt__ and those computed from it)
    def __le__(self, other: "Word") -> bool:
        print("ShortFirst.__le__")
        return (len(self.s), self.s) <= (len(other.s), other.s)


@dataclass(order=True)
class Version:
    major: int
    minor: int


@total_ordering
@dataclass
class Tagged(Version):
    # (@dataclass without order=True adds no ordering method: >= is its own, the others Version's)
    label: str = ""

    def __ge__(self, other: "Version") -> bool:
        print("Tagged.__ge__")
        return self.major >= other.major


a, b = ShortFirst("zz"), ShortFirst("aaa")
print(a < b, a <= b, a > b, a >= b)
print(b < a, b <= a, b > a, b >= a)
print(sorted([b, a])[0].s)
v, w = Tagged(1, 5, "v"), Tagged(1, 2, "w")
print(v < w, v <= w, v > w, v >= w)
print(w >= v, max(v, w).label, sorted([v, w])[0].label)
