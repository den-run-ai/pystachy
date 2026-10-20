# error: generic_noinit_base.py:12: error: a generic class with another base than Generic[...] is not supported
from typing import Generic, TypeVar

T = TypeVar("T")


class Base:
    def __init__(self) -> None:
        self.n = 1


class Box(Generic[T], Base):
    pass


print(Box[int]().n)
