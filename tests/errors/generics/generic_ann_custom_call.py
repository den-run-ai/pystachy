# error: Box[...] with a custom __class_getitem__ is not supported
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def __class_getitem__(cls, item: int) -> None:
        print("custom")


value = Box[int](1)
