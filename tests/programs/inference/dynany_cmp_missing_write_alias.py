# pystachy: dynamic-any
from typing import Any

class A:
    def __init__(self) -> None:
        self.items = [3]
    def __eq__(self, other: "A") -> bool:
        print("comparison ran")
        peer = other
        peer.items = self.items
        peer.items.append(4)
        return other.items is self.items
class B:
    pass
original = A()
x: Any = original
y: Any = B()
print(x == y)
print(original.items)
