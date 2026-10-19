from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    @property
    def __weird__(self) -> int:
        return 1
