# pystachy: dynamic-any
# A closure's own parameters and captured operand aliases retain their origins.
from typing import Any


class Left:
    def __init__(self) -> None:
        self.items = [1, 2]

    def __eq__(self, other: "Left") -> bool:
        print("comparison ran")
        original = other

        def compare(peer) -> bool:
            print("local helper ran")
            return self.items == peer.items

        def captured() -> bool:
            print("captured helper ran")
            return compare(original)

        return captured()


class Right:
    def __init__(self) -> None:
        self.items = ["1", "2"]


left: Any = Left()
right: Any = Right()
print(left == right)
print(right == left)
print(left != right)
