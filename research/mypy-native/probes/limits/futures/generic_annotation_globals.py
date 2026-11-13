from typing import Generic, TypeVar

_T = TypeVar("_T")

READY = "ready"


class Box(Generic[_T]):
    def __init__(self, item: _T | None = None) -> None:
        self.item = item
        self.state: str = READY

    def __repr__(self) -> str:
        if self.state == READY:
            return "<Box ready>"
        return "<Box>"


def show(b: Box[int]) -> None:
    print(b)


show(Box(1))
