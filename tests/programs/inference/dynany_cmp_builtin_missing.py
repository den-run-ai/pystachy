# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self) -> None:
        self.items: list[str] = []


class Strict:
    def __init__(self) -> None:
        self.items: list[int] = []
        self.marker = 1

    def __eq__(self, other: "Strict") -> bool:
        print("entered")
        return self.items == other.items and self.marker == other.marker


strict = Strict()
x: Any = strict
y: Any = Peer()
try:
    print(x == y)
except AttributeError as exc:
    print(str(exc))
# A differing list content short-circuits the missing field's read.
strict.items.append(3)
try:
    print(x == y)
except AttributeError as exc:
    print(str(exc))
