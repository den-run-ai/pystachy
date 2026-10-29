# pystachy: dynamic-any
from typing import Any


class Words:
    def __init__(self, filled: bool) -> None:
        self.items: set[tuple[str, str]] = set()
        if filled:
            self.items.add(("", ""))


class Numbers:
    def __init__(self, filled: bool) -> None:
        self.items: set[tuple[int, int]] = set()
        if filled:
            self.items.add((0, 0))

    def __eq__(self, other: "Numbers") -> bool:
        print("tuple sets ran")
        return self.items == other.items


for filled in [False, True]:
    numbers = Numbers(filled)
    words = Words(filled)
    x: Any = numbers
    y: Any = words
    print(x == y, y == x, x != y, y != x, y in [x])
    print(numbers == Numbers(filled))
    numbers.items.add((1, 2))
    words.items.add(("one", "two"))
    print(len(numbers.items), len(words.items))
