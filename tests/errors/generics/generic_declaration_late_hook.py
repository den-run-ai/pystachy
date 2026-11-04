# error: the special method __getattribute__ is not supported (CPython calls it to read each attribute)
from __future__ import annotations
from typing import Generic, TypeVar

T = TypeVar("T")


class Cell(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def take(self, other: Cell[int]) -> int:
        return other.value

    def __getattribute__(self, name: str) -> int:
        return 42


cell = Cell(1)
print(cell.value)
