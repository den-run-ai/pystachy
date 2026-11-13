from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item

    def __repr__(self) -> str:
        return READY


def show(box: Box[int]) -> None:
    print(box)


try:
    show(Box(1))
except NameError:
    print("unbound")
READY = "ready"
show(Box(2))
