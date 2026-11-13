# error: expected str, got int
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item

    def __repr__(self) -> str:
        return 1


def show(box: Box[int]) -> None:
    print(box)


show(Box(1))
