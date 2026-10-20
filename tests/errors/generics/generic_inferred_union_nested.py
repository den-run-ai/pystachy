# error: Pair() cannot bind its type variables from the argument for 'b', a str: 'T' is int already, and str here
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, a: list[T], b: T) -> None:
        self.a = a
        self.b = b


xs = [1]
print(Pair(xs, "s").a)
