# pystachy: dynamic-any
# Remaining #803 gap: incompatible typed field layouts still fall outside the
# guarded structural adapter, so this comparison skips the method side effect.
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items = ["different storage"]


class Strict:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Strict") -> bool:
        print("comparison ran")
        return self.items == other.items


x: Any = Strict()
y: Any = Peer()
try:
    print(x == y)
except AttributeError:
    print("missing items")
