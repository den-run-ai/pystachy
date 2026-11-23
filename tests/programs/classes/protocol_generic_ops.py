# A generic Protocol's values compare, hash, format and narrow by their objects too, and so do
# the Iterator[T] values that joins of distinct iterators give.
from typing import Iterator, Protocol, TypeVar

T = TypeVar("T")


class Cell(Protocol[T]):
    def get(self) -> T: ...


class IntCell:
    def __init__(self, v: int) -> None:
        self.v = v

    def get(self) -> int:
        return self.v

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IntCell):
            return NotImplemented
        return self.v == other.v

    def __hash__(self) -> int:
        return hash(self.v)


class Fixed:
    def get(self) -> int:
        return 7


def gen() -> Iterator[int]:
    yield 1


cells: list[Cell[int]] = [IntCell(1), IntCell(1), Fixed()]
print(cells[0] == cells[1], cells[0] == cells[2], cells[2] != cells[2], hash(cells[0]) == hash(1))
print([c.get() for c in cells if isinstance(c, IntCell)], f"{cells[0].get():>3}")
it = iter([1, 2]) if len(cells) > 5 else gen()
print(next(it), isinstance(it, Fixed))
