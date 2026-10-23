# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, value: int) -> None:
        self.items = [value]


class Ordered:
    def __init__(self, value: int) -> None:
        self.items = [value]

    def __lt__(self, other) -> bool:
        print("lt")
        return self.items < other.items

    def __le__(self, other: object) -> bool:
        print("le")
        return self.items <= other.items

    def __gt__(self, other: "Ordered") -> bool:
        print("gt")
        return self.items > other.items

    def __ge__(self, other: "Ordered") -> bool:
        print("ge")
        return self.items >= other.items

    def __ne__(self, other: "Ordered") -> bool:
        print("ne")
        return self.items != other.items


x: Any = Ordered(3)
y: Any = Peer(4)
print(x < y, y > x)
print(x <= y, y >= x)
print(x > y, y < x)
print(x >= y, y <= x)
print(x != y, y != x)
