# The result of bool arithmetic is int; it need not share the fields' TypeVar.
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T) -> None:
        self.left = left
        self.right = right

    def total(self) -> int | float:
        return self.left + self.right

    def total_bound(self) -> T:
        return self.left + self.right


pair = Pair(True, 2.5)
print(pair.total())
pair.right = False
print(pair.total())

wide: Pair[bool | int | float] = Pair(True, 2.5)
print(wide.total_bound())
wide.right = False
print(wide.total_bound())
