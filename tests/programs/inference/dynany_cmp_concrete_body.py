# pystachy: dynamic-any
# The Any specialization cannot box typed container fields. Guard the concrete
# operand class and execute the original body with those fields still typed.
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
