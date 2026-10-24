# pystachy: dynamic-any
from typing import Any


def retained(values):
    print("helper")
    return values


class Peer:
    def __init__(self, fail: bool = False) -> None:
        self.saved = ["a", "b"]
        self.fail = fail

    @property
    def items(self):
        print("getter")
        try:
            if self.fail:
                raise LookupError("getter error")
            values = retained(self.saved)
            return values
        finally:
            print("getter cleanup")


class Record:
    def __init__(self, fail: bool = False) -> None:
        self.items = [1, 2]
        self.fail = fail

    def __eq__(self, other: "Record") -> bool:
        print("comparison")
        try:
            if self.fail:
                raise ValueError("first error")
            return len(other.items) == len(self.items)
        finally:
            print("comparison cleanup")


peer = Peer()
record = Record()
x: Any = record
y: Any = peer
print(x == y, y == x, x != y, y in [x])
values = peer.items
values.append("c")
print(values is peer.saved, x == y, peer.saved)
print(record == Record())

for fail_first in [False, True]:
    x = Record(fail_first)
    y = Peer(True)
    try:
        print(x == y)
    except LookupError as exc:
        print(str(exc))
    except ValueError as exc:
        print(str(exc))
