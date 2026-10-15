# error: Pair() cannot bind its type variables from the argument for 'right', a str: 'T' is int already, and str here
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T) -> None:
        self.left = left
        self.right = right


Pair[int | float](1, "bad")
