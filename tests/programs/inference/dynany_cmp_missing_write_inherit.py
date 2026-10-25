# pystachy: dynamic-any
from typing import Any

class Root:
    def __init__(self) -> None:
        self.count = 6
class B(Root):
    def __init__(self) -> None:
        super().__init__()
        self.tail = "tail"
class A:
    def __init__(self) -> None:
        self.items = [3]
    def __eq__(self, other: "A") -> bool:
        print("comparison ran")
        other.items = self.items
        return other.items is self.items
original = B()
x: Any = A()
y: Any = original
print(x == y)
print(original.count, original.tail)
