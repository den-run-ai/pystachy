# pystachy: dynamic-any
from typing import Any


class Left:
    def __init__(self, value: int):
        self.value = value

    def __eq__(self, other: Any) -> bool:
        print("element")
        return self.value == other.value


class Right:
    def __init__(self, value: int):
        self.value = value


class Strict:
    def __init__(self):
        self.items = [Left(3)]

    def __eq__(self, other: "Strict") -> bool:
        print("comparison")
        return self.items == other.items


class Peer:
    def __init__(self):
        self.items = [Right(3)]


strict = Strict()
peer = Peer()
left: Any = strict
right: Any = peer
print(left == right, right == left, left != right, right in [left])
peer.items[0].value = 4
print(left == right, right == left)
print(strict == Strict())
