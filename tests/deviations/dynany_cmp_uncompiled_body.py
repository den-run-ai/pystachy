# pystachy: dynamic-any
# Remaining #803 gap: this body also fails for the concrete operand class,
# because Peer has no items attribute. The fallback still skips its side effect
# and AttributeError, although concrete adapters now support typed fields.
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
