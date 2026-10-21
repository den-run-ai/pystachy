# error: generic_ann_forward.py:7: error: Box[...] names a generic class that is declared further down: Pystachy needs its class statement before the annotation
from typing import Generic, Iterable, TypeVar

T = TypeVar("T")


def total(b: "Box[int]") -> int:
    return sum(b.items)


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self.items: list[T] = list(items)


print(total(Box([1, 2, 3])))
