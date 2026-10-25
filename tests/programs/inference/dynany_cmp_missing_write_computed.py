# pystachy: dynamic-any
from typing import Any


first = [1]
second = ["two"]


def produce() -> list[int]:
    print("rhs")
    return first


class Peer:
    pass


class Writer:
    def __eq__(self, other) -> bool:
        print("body")
        other.flag = True
        other.items = None
        print(other.items is None)
        print(other.items is other.items, other.items is not other.items)
        other.items = produce()
        print(other.items is first)
        other.items = second
        return other.flag and other.items is second and second is other.items and other.items is not first

    def __lt__(self, other: Any) -> bool:
        print("ordered")
        other.marker = None
        other.count = len(second)
        return other.marker is None and other.count == 1


writer = Writer()
peer = Peer()
untouched = Peer()
x: Any = writer
y: Any = peer
z: Any = untouched
print(vars(writer), vars(peer), vars(untouched))
print(hasattr(peer, "flag"), hasattr(peer, "items"))
print(x == y)
print(x < y)
print(hasattr(peer, "flag"), hasattr(peer, "items"))
print(y.flag, y.count, y.marker is None)
print(hasattr(untouched, "flag"), vars(untouched), vars(writer))
second.append("three")
print(first, second)
