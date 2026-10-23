# pystachy: dynamic-any
# A missing field raises only when the comparison body reaches the read.
from typing import Any


class Peer:
    pass


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
