from typing import Generic, TypeVar

_T = TypeVar("_T")

READY = "ready"


class Box(Generic[_T]):
    def __init__(self, item: _T) -> None:
        self.item = item

    def __repr__(self) -> str:
        return READY


def show(b: Box[int]) -> None:
    print(b)


show(Box(1))
