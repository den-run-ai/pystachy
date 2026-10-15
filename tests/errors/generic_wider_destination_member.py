# error: expected Box[int | str], got Box[float]
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


box: Box[int | str] = Box(1.5)
