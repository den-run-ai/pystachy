# error: generic_ann_mismatch.py:12: error: expected Box[int], got Box[str]
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self.items: list[T] = list(items)


b: Box[int] = Box(["a"])
