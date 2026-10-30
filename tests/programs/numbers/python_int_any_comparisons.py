# pystachy: python-int
# pystachy: dynamic-any
# Concrete comparison bodies keep numeric fields, effects and nested properties.
from typing import Any


class IntLeaf:
    def __init__(self, value: int) -> None:
        self.value = value

    @property
    def amount(self) -> int:
        print("int property")
        return self.value


class FloatLeaf:
    def __init__(self, value: float) -> None:
        self.value = value

    @property
    def amount(self) -> float:
        print("float property")
        return self.value


class Strict:
    def __init__(self, fail: bool = False) -> None:
        self.items = [3]
        self.total = 0
        self.fail = fail
        self.nodes = [IntLeaf(2 ** 70 + 1)]
        self.index = int("0")

    @property
    def count(self) -> int:
        print("count get")
        return self.total

    @count.setter
    def count(self, value: int) -> None:
        print("count set", value)
        self.total = value

    def __eq__(self, other: "Strict") -> bool:
        print("equality")
        other.count += 1
        if self.fail:
            raise ValueError("first error")
        return self.items == other.items

    def __lt__(self, other: "Strict") -> bool:
        print("ordering", self.items == other.items)
        return -(self.nodes[self.index].amount + 1) < -(other.nodes[other.index].amount + 1)


class Peer:
    def __init__(self) -> None:
        self.items = ["three"]
        self.count = 9223372036854775807
        self.nodes = [FloatLeaf(float(2 ** 70))]
        self.index = 0


class Missing:
    def __init__(self) -> None:
        self.count = 9223372036854775807


strict = Strict()
peer = Peer()
left: Any = strict
right: Any = peer
print(left == right, right == left, left != right)
print(peer.count)
print(left < right, right > left)
print(strict == Strict())
print(strict.items, peer.items)

missing = Missing()
right = missing
left = Strict(True)
try:
    print(left == right)
except ValueError as error:
    print(error)
print(missing.count)
left = Strict()
try:
    print(right == left)
except AttributeError as error:
    print(error)
print(missing.count)
