# error: protocol_union.py:23: error: expected Shape, got Circ | Sq: a union's value converts once narrowed to one class (isinstance() first), not as Circ | Sq
from typing import Protocol


class Shape(Protocol):
    def area(self) -> float: ...


class Sq:
    def area(self) -> float:
        return 4.0


class Circ:
    def area(self) -> float:
        return 3.0


def pick(flag: bool) -> Sq | Circ:
    return Sq() if flag else Circ()


s: Shape = pick(True)
print(s.area())
