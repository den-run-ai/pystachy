# pystachy: dynamic-any
from typing import Any
class A:
    def __init__(self) -> None:
        self.items = [3]
    def __eq__(self, other: "A") -> bool:
        print("comparison ran")
        try:
            print(len(other.items))
        except AttributeError:
            print("missing")
        other.items = self.items
        return other.items is self.items
class B:
    pass
x: Any = A()
y: Any = B()
z: Any = B()
print(x == y)
print(x == y)
print(x == z)
