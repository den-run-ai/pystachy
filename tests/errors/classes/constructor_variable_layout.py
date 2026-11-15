# error: inheritance with generic class templates is not supported
from typing import Iterable


class Stored:
    def __init__(self, values: Iterable[int]) -> None:
        self.values: Iterable[int] = values


class Child(Stored):
    pass


print(Child([1]).values)
