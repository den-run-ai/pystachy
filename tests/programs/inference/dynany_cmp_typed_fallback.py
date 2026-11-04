# pystachy: dynamic-any
# Keep the supported typed call across unrelated classes when their native
# integer-list fields can also be reached through an Any specialization.
from typing import Any


class Peer:
    def __init__(self, n: int) -> None:
        self.items = [n]


class Strict:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __eq__(self, other: Peer) -> bool:
        print("typed comparison")
        return self.items == other.items


x: Any = Strict(3)
same: Any = Peer(3)
different: Any = Peer(4)
print(x == same, same == x, x != different)
