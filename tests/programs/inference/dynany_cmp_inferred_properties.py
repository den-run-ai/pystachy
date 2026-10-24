# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, empty: bool, fail: bool = False) -> None:
        self.saved: list[str] = [] if empty else ["three"]
        self.fail = fail
        self.calls = 0

    @property
    def items(self):
        self.calls += 1
        print("getter", self.calls)
        if self.fail:
            raise LookupError("getter error")
        if self.calls == 2:
            return self.saved
        return self.saved


class Numbers:
    def __init__(self, empty: bool, fail: bool = False) -> None:
        self.items: list[int] = [] if empty else [3]
        self.fail = fail

    def __eq__(self, other: "Numbers") -> bool:
        print("comparison")
        if self.fail:
            raise ValueError("first error")
        return self.items == other.items


for empty in [False, True]:
    numbers = Numbers(empty)
    peer = Peer(empty)
    x: Any = numbers
    y: Any = peer
    print(x == y, y == x, x != y, y in [x])
    peer.saved.append("four")
    print(x == y, peer.saved, numbers.items)
    print(numbers == Numbers(empty))

x = Numbers(True)
y = Peer(True, True)
try:
    print(x == y)
except LookupError as exc:
    print(str(exc))
x = Numbers(True, True)
try:
    print(x == y)
except ValueError as exc:
    print(str(exc))


class Box:
    def __init__(self, values):
        self.saved = values

    @property
    def items(self):
        print("template getter")
        return self.saved


words: list[str] = []
x = Numbers(True)
y = Box(words)
print(x == y)
words.append("changed")
print(x == y)
