# A generic class's field of an explicit int | float, given a float after an int.
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T) -> None:
        self.left = left
        self.right = right


pair = Pair[int | float](1, 2)
print(pair.left, pair.right)
pair.right = 2.5
print(pair.left, pair.right)
