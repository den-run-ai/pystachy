# An early self signature still needs the later class-attribute declaration pass.
from __future__ import annotations
from typing import Generic, TypeVar

T = TypeVar("T")


class Cell(Generic[T]):
    kind: str = "s"

    def __init__(self, value: T) -> None:
        self.value = value

    def take(self, other: Cell[int]) -> int:
        return other.value


def read_kind(value: Cell[int]) -> str:
    return value.kind


cell = Cell(1)
print(cell.value, cell.kind)
