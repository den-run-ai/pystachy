# pystachy: dynamic-any
# Comparison writes reserve unassigned native storage without losing effects.
from typing import Any


class Peer:
    pass


class Strict:
    def __init__(self) -> None:
        self.items = [3, 4]

    def __eq__(self, other: "Strict") -> bool:
        print("comparison ran")
        other.items = self.items
        return other.items == self.items


x: Any = Strict()
y: Any = Peer()
print(x == y)
