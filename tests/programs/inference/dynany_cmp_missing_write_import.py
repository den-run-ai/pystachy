# pystachy: dynamic-any
from typing import Any
from plain_comparison_peer import Child, Peer, read


class Writer:
    def __init__(self) -> None:
        self.items = [3]

    def __eq__(self, other: "Writer") -> bool:
        print("comparison ran")
        other.items = self.items
        return other.items is self.items


original = Child()
untouched = Peer(9)
writer = Writer()
x: Any = writer
y: Any = original
z: Any = untouched
print(vars(untouched))
print(read(original), original.tail)
print(hasattr(original, "items"))
print(x == y)
print(read(original), original.tail)
print(vars(untouched))
print(hasattr(original, "items"))
print(original.items is writer.items)
original.items.append(4)
print(writer.items)
