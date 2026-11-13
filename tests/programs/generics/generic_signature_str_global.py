from typing import Generic, TypeVar

T = TypeVar("T")
READY: str = "ready"


class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item

    def __str__(self) -> str:
        return READY


def show(box: Box[int]) -> None:
    print(box)


show(Box(1))
READY = "changed"
show(Box(2))
