# objects of class templates' specializations and of generic classes as dict keys and set
# elements: each specialization is a class of its own, hashed by identity or by its __hash__
from typing import Generic, TypeVar

T = TypeVar("T")


class Box:
    def __init__(self, v):
        self.v = v

    def __repr__(self) -> str:
        return f"Box({self.v!r})"


class Cell(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cell) and self.v == other.v

    def __hash__(self) -> int:
        return hash(self.v)

    def __repr__(self) -> str:
        return f"Cell({self.v!r})"


b1 = Box(1)
b2 = Box("s")
d1 = {b1: "int"}
d2 = {b2: "str"}
print(d1[b1], d2[b2], Box(1) in d1, d1, d2)
c1: dict[Cell[int], int] = {Cell(1): 1}
c1[Cell(5)] = 5
c1[Cell(1)] += 10
print(c1[Cell(1)], Cell(2) in c1, c1, {Cell("a"), Cell("a")}, {Cell(3), Cell(1), Cell(2)})
print(sorted([str(k) for k in {Box(3): 1}]), max({Cell(4): 0, Cell(9): 1}, key=lambda c: c.v))
print(hash(Cell(7)) == hash(7), hash(Cell("x")) == hash("x"), hash(Cell((1, 2))))
