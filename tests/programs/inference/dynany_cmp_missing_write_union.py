# pystachy: dynamic-any
from typing import Any
class B:
    pass
class A:
    def __init__(self) -> None:
        self.items = [3]
    def __eq__(self, other: "A") -> bool:
        print("A ran")
        other.items = self.items
        return other.items is self.items
class C:
    def __init__(self) -> None:
        self.items = ["3"]
    def __eq__(self, other: "C") -> bool:
        print("C ran")
        other.items = self.items
        return other.items is self.items
x: Any = A()
y: Any = B()
z: Any = C()
print(x == y)
print(z == y)
print(x == y)
