# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, empty: bool) -> None:
        self.items: list[float] = [] if empty else [3.0]
        self.lookup = {"value": 3.0}


class Numbers:
    def __init__(self, fail: bool = False) -> None:
        self.items = [3]
        self.lookup = {"value": 3}
        self.fail = fail

    def __eq__(self, other: "Numbers") -> bool:
        print("indexed eq")
        if self.fail:
            raise ValueError("first error")
        return self.items[0] + other.items[0] == self.lookup["value"] * 2

    def __ne__(self, other: "Numbers") -> bool:
        print("indexed ne")
        return self.lookup["value"] != other.lookup["value"]

    def __lt__(self, other: "Numbers") -> bool:
        print("indexed lt")
        return self.items[0] - 1 < other.items[0]

    def __le__(self, other: "Numbers") -> bool:
        print("indexed le")
        return self.items[0] / 2 <= other.items[0]

    def __gt__(self, other: "Numbers") -> bool:
        print("indexed gt")
        return self.items[0] * 2 > other.items[0]

    def __ge__(self, other: "Numbers") -> bool:
        print("indexed ge")
        return self.items[0] >= other.items[0] // 2


numbers = Numbers()
peer = Peer(False)
x: Any = numbers
y: Any = peer
print(x == y, y == x, x != y, y != x)
print(x < y, y > x, x <= y, y >= x)
print(x > y, y < x, x >= y, y <= x)
print(y in [x], [x].count(y), [x].index(y))
print(numbers == Numbers())
peer.items[0] = 4.0
numbers.items[0] = 4
print(peer.items, numbers.items, x == y)
y = Peer(True)
try:
    print(x == y)
except IndexError as exc:
    print(str(exc))
x = Numbers(True)
try:
    print(x == y)
except ValueError as exc:
    print(str(exc))
