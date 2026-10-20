# error: expected int | str, got bool
# A generic union context must still contain every member of the display.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


value = Box[list[int | str]]([True, 1])
