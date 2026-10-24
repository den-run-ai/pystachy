# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, fail: bool) -> None:
        self.saved = [3]
        self.fail = fail
        self.calls = 0

    @property
    def items(self) -> list[int]:
        self.calls += 1
        print("getter", self.calls)
        if self.fail:
            raise LookupError("getter error")
        return self.saved


class Words:
    @property
    def items(self) -> list[str]:
        print("words getter")
        return ["three"]


class Numbers:
    def __init__(self, fail: bool = False) -> None:
        self.items = [3]
        self.fail = fail

    def __eq__(self, other: "Numbers") -> bool:
        print("property comparison")
        if self.fail:
            raise ValueError("first error")
        return self.items == other.items


peer = Peer(False)
numbers = Numbers()
x: Any = numbers
y: Any = peer
print(x == y, y == x, x != y, y in [x])
peer.saved.append(4)
print(x == y, peer.saved, numbers.items)
y = Words()
print(x == y, y == x, x != y)
y = Peer(True)
try:
    print(x == y)
except LookupError as exc:
    print(str(exc))
x = Numbers(True)
try:
    print(x == y)
except ValueError as exc:
    print(str(exc))
