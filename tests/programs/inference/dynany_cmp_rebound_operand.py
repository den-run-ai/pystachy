# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items: list[str] = ["different storage"]


class Rebound:
    def __init__(self, fail: bool = False) -> None:
        self.items: list[int] = [3]
        self.fail = fail

    def __eq__(self, other: "Rebound") -> bool:
        print("eq entered")
        if self.fail:
            raise ValueError("prefix error")
        other = self
        return self.items == other.items

    def __ne__(self, other: "Rebound") -> bool:
        alias = other
        print("ne entered")
        alias = self
        return self.items != alias.items

    def __lt__(self, other: "Rebound") -> bool:
        print("lt entered")
        other = self
        return self.items < other.items

    def __le__(self, other: "Rebound") -> bool:
        print("le entered")
        other = self
        return self.items <= other.items

    def __gt__(self, other: "Rebound") -> bool:
        print("gt entered")
        other = self
        return self.items > other.items

    def __ge__(self, other: "Rebound") -> bool:
        print("ge entered")
        other = self
        return self.items >= other.items


x: Any = Rebound()
y: Any = Peer()
print(x == y, y == x)
print(x != y, y != x)
print(x < y, y > x)
print(x <= y, y >= x)
print(x > y, y < x)
print(x >= y, y <= x)
number: Any = 7
print(x == number, number == x)
print([x].count(y), y in [x])
print(x.__eq__(x), x.__ne__(x))
fail: Any = Rebound(True)
try:
    print(fail == y)
except ValueError as exc:
    print(str(exc))
