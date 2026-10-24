# pystachy: dynamic-any
from typing import Any


class Left:
    def __init__(self) -> None:
        self.items = [1]

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        original = other
        for step in range(2):
            print("before", step, len(other.items), len(original.items))
            if len(other.items) > 1:
                other = self
            print("after", step, len(other.items), len(original.items))
        return self.items == other.items


class Right:
    def __init__(self, two: bool) -> None:
        self.items = ["x", "y"] if two else ["x"]


for two in [True, False]:
    a: Any = Left()
    b: Any = Right(two)
    print(a == b)
    print(b == a)
    print(a != b)
