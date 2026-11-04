# Preserve the existing provisional path for a recursive class-attribute annotation.
from typing import Generic, TypeVar

T = TypeVar("T")


class Cell(Generic[T]):
    other: "Cell[int] | None" = None

    def __init__(self, value: T) -> None:
        self.value = value


first = Cell(1)
second = Cell[int](2)
word = Cell("s")
print(first.value, first.other, second.value, second.other, word.value, word.other)
