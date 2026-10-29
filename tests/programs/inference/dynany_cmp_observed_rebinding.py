# pystachy: dynamic-any
from typing import Any

saved: list[Any] = []


class Left:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Left") -> bool:
        print("comparison", len(other.items))
        alias = other
        saved.append(alias)
        other = self
        print("rebound", len(other.items), len(alias.items))
        alias.items.clear()
        return self.items == other.items and len(alias.items) == 0


class Right:
    def __init__(self) -> None:
        self.items = ["x", "y"]


left: Any = Left()
right: Any = Right()
print(left == right)
print(saved[0] is right)
right2: Any = Right()
print(right2 == left)
print(saved[1] is right2)
print(left != Right())
