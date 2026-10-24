# pystachy: dynamic-any
# Remaining #803 gap: concatenating differently typed lists still falls outside
# the guarded adapter, so this comparison skips the method side effect.
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items = ["different", "storage"]


class Strict:
    def __init__(self) -> None:
        self.items = [3, 4]

    def __eq__(self, other: "Strict") -> bool:
        print("comparison ran")
        return len(self.items + other.items) > 0


x: Any = Strict()
y: Any = Peer()
try:
    print(x == y)
except AttributeError:
    print("missing items")
