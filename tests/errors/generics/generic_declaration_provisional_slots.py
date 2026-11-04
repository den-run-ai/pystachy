# error: unsupported type annotation
# Keep the existing provisional-signature limitation until slot metadata is ready.
from __future__ import annotations
from typing import Generic, TypeVar

T = TypeVar("T")


class Cell(Generic[T]):
    __slots__ = ("value",)

    def __init__(self, value: T) -> None:
        self.value = value

    def take(self, other: Cell[int]) -> int:
        return other.value


cell = Cell(1)
print(cell.value, hasattr(cell, "__dict__"))
