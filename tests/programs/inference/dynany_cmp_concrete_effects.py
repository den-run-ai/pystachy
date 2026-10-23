# pystachy: dynamic-any
from typing import Any


class Peer:
    def __init__(self, value: int) -> None:
        self.label = "different layout"
        self.count = 12
        self.items = [value]


class Strict:
    def __init__(self, value: int) -> None:
        self.items = [value]

    def __eq__(self, other: "Strict") -> bool:
        print("eq", self.items[0])
        equal = self.items == other.items
        if self.items[0] < 0:
            raise ValueError("comparison failed")
        other.items.append(8)
        return equal


left = Strict(3)
right = Peer(3)
x: Any = left
y: Any = right
print(x == y)
print(right.items)
right.items.pop()
print(y == x)
print(right.items)
right.items.pop()
print(x != y)
print(right.items)
bad: Any = Strict(-1)
try:
    print(bad == y)
except ValueError as exc:
    print(str(exc))
print(right.items)

# Container equality/search invokes the same adapter, keeping aliases intact.
right.items.pop()
print(y in [x])
print(right.items)


class Inherited(Strict):
    pass


right.items.pop()
child: Any = Inherited(3)
print(child == y)
print(right.items)
