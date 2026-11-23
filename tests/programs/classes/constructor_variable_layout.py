# A field annotated Iterable[int] holds the value it is given, list or other: the class is a
# template, from which a class without an __init__ of its own derives (#962)
from typing import Iterable


class Stored:
    def __init__(self, values: Iterable[int]) -> None:
        self.values: Iterable[int] = values


class Child(Stored):
    pass


print(Child([1]).values)
