# An early self annotation must not fix the layout before a later property setter.
from __future__ import annotations
from typing import Generic, TypeVar

T = TypeVar("T")


class Cell(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def take(self, other: Cell[int]) -> int:
        return other.value

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, item: T) -> None:
        self._value = item


cell = Cell(1)
print(cell.value)
cell.value = 2
print(cell.value)
