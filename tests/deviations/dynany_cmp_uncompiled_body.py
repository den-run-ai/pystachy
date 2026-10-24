# pystachy: dynamic-any
# Remaining #803 gap: a comparison cannot add missing instance storage to a peer.
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
