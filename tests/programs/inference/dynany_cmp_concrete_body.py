# pystachy: dynamic-any
# Native integer-list fields can share their storage with the Any specialization.
# A concrete operand annotation must still allow an unrelated matching class.
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items = [3]


class Strict:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Strict") -> bool:
        print("comparison ran")
        return self.items == other.items


x: Any = Strict()
y: Any = Peer()
print(x == y)
