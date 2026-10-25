# pystachy: dynamic-any
# The helper graph may recur with stable or swapped native operand origins.
from typing import Any


def descend(left, right, count: int) -> bool:
    print("descend", count)
    if count > 0:
        return descend(left, right, count - 1)
    return left.items == right.items


def first(left, right, count: int) -> bool:
    print("first", count)
    if count > 0:
        return second(right, left, count - 1)
    return left.items == right.items


def second(left, right, count: int) -> bool:
    print("second", count)
    if count > 0:
        return first(right, left, count - 1)
    return left.items == right.items


class Left:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Left") -> bool:
        print("comparison ran")
        a = descend(self, other, 2)
        b = first(self, other, 2)
        return a or b


class Right:
    def __init__(self) -> None:
        self.items = ["3"]


left: Any = Left()
right: Any = Right()
print(left == right)
