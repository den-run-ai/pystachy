# error: an annotation that is not a type is not supported
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def __class_getitem__(cls, item: int) -> None:
        print("custom")


def use(value: Box[int]) -> None:
    pass
