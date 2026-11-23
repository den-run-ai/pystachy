# hash() of a Protocol value is its object's: its class's __hash__, else its identity's, and
# CPython's TypeError for a class that defines __eq__ alone; also inside a tuple and in a frozen
# dataclass, whose __eq__ and __repr__ compare and print the object.
from dataclasses import dataclass
from typing import Protocol


class Shape(Protocol):
    def area(self) -> float: ...


class Square:
    def __init__(self, side: float) -> None:
        self.side = side

    def area(self) -> float:
        return self.side * self.side

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Square):
            return NotImplemented
        return self.side == other.side

    def __hash__(self) -> int:
        print("Square.__hash__")
        return hash(self.side)

    def __repr__(self) -> str:
        return f"Square({self.side})"


class Circle:
    def __init__(self, r: float) -> None:
        self.r = r

    def area(self) -> float:
        return 3.0 * self.r * self.r

    def __repr__(self) -> str:
        return f"Circle({self.r})"


class Blob:
    def area(self) -> float:
        return 0.0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Blob):
            return NotImplemented
        return self is other


@dataclass(frozen=True)
class Placed:
    shape: Shape
    x: int


circle = Circle(1.0)
a: Shape = circle
b: Shape = Square(2.0)
print(hash(a) == hash(circle), hash(b) == hash(2.0), hash(b) == hash(Square(2.0)))
print(hash((b, 1)) == hash((2.0, 1)), hash((a, (b, "s"))) == hash((circle, (2.0, "s"))))
n: Shape | None = None
print(hash(n) == hash(None), hash((n, b)) == hash((None, 2.0)))
u: Shape = Blob()
try:
    print(hash(u))
except TypeError as e:
    print("TypeError:", e)
p = Placed(Square(1.0), 2)
q = Placed(Square(1.0), 2)
r = Placed(circle, 2)
print(p == q, p == r, p != r, hash(p) == hash(q), hash(r) == hash((circle, 2)))
print(p, r)
