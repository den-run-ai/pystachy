# error: Pair() cannot bind its type variables from the argument for 'b', a list[str]: 'T' is list[int] already, and list[str] here
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, a: T, b: T) -> None:
        self.both: list[T] = [a, b]


print(Pair([1], ["x"]).both)
