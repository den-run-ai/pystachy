# error: expected Box[float | int], got Box[int]
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


narrow = Box(1)
wide: Box[int | float] = narrow
