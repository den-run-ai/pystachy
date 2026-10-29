# pystachy: dynamic-any
from typing import Any


def replacement(value):
    owner = value
    result = owner.replacement
    return result


class Left:
    def __init__(self) -> None:
        self.items = [1]
        self.total = 0

    @property
    def replacement(self) -> list[int]:
        print("replacement")
        return self.items

    @property
    def count(self) -> int:
        print("left get")
        return self.total

    @count.setter
    def count(self, value: int) -> None:
        print("left set", value)
        self.total = value

    def __eq__(self, other: "Left") -> bool:
        print("comparison")
        original = other
        if len(other.items) > 1:
            other = self
        other.count += 2
        other.items = replacement(self)
        print("original", len(original.items), original.count)
        return other.items is self.items


class Right:
    def __init__(self) -> None:
        self.saved_items = ["one", "two"]
        self.total = 10

    @property
    def items(self) -> list[str]:
        print("right items get")
        return self.saved_items

    @items.setter
    def items(self, value: list[str]) -> None:
        print("right items set")
        self.saved_items = value

    @property
    def count(self) -> int:
        print("right get")
        return self.total

    @count.setter
    def count(self, value: int) -> None:
        print("right set", value)
        self.total = value


class Same:
    def __init__(self) -> None:
        self.items = [2]
        self.count = 20


left = Left()
right = Right()
a: Any = left
b: Any = right
print(a == b)
print(left.items, right.items, left.total, right.total)
same = Same()
c: Any = same
print(a == c)
print(same.items is left.items, same.count)
