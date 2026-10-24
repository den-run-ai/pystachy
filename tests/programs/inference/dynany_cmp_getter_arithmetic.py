# pystachy: dynamic-any
from typing import Any


class Numbers:
    def __init__(self) -> None:
        self.values = [1]

    @property
    def items(self):
        print("numbers getter")
        result = self.values + [2]
        return result

    def __eq__(self, other: "Numbers") -> bool:
        print("comparison")
        return self.items == other.items


class Words:
    def __init__(self) -> None:
        self.values = ["one"]

    @property
    def items(self):
        print("words getter")
        return self.values + ["two"]


left: Any = Numbers()
right: Any = Words()
print(left == right, right == left, left != right)
print(Numbers().items, Words().items)
