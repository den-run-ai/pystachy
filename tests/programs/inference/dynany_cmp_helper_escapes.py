# pystachy: dynamic-any
from typing import Any

saved: list[Any] = []


def equal_items(a, b) -> bool:
    print("helper", len(b.items))
    return a.items == b.items


def forward(a, b) -> bool:
    print("forward")
    return equal_items(a, b)


class Left:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        saved.append(other)
        return forward(self, other)


class Right:
    def __init__(self) -> None:
        self.items = ["x", "y"]


left: Any = Left()
right: Any = Right()
print(left == right)
print(saved[0] is right)
print(right == left)
print(saved[1] is right)
print(left != right)
print(saved[2] is right)
print([left].count(right))
print(saved[3] is right)
