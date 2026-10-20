# error: argument for 'right', a float: 'T' is int already, and float here
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: list[T], right: T = 2.5) -> None:
        self.left = left
        self.right = right


Pair[int | float]([1])
