# pystachy: dynamic-any
from typing import Any
saved: Any = None
class A:
    def __init__(self) -> None:
        self.items = [1]
    def __eq__(self, other: "A") -> bool:
        print("comparison ran")
        global saved
        saved = other
        return self.items == other.items
class B:
    def __init__(self) -> None:
        self.items = ["1"]
        self.count = 1
original = B()
x: Any = A()
y: Any = original
print(x == y)
saved.count += 1
print(original.count)
