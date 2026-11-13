from typing import Generic, TypeVar

T = TypeVar("T")
READY = "module-ready"


class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item

    def __repr__(self) -> str:
        return READY
