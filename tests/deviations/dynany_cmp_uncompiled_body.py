# pystachy: dynamic-any
# Retained #803 deviation: comparing a typed container with an Any field cannot
# compile. The dynamic comparison still declines that body, although CPython
# runs it and prints "comparison ran" followed by True.
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
