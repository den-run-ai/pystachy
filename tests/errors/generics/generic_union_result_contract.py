# error: expected bool | float, got float | int
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T) -> None:
        self.left = left
        self.right = right

    def total(self) -> T:
        return self.left + self.right


print(Pair(True, 2.5).total())
