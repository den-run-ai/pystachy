# error: expected int, got float
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T) -> None:
        self.left = left
        self.right = right


pair = Pair[int | float](1, 2)
pair.right = 2.5
