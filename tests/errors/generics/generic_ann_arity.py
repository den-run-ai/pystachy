# error: generic_ann_arity.py:12: error: Box[...] takes 1 type (T), not 2
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self.items: list[T] = list(items)


b: Box[int, str] = Box()
