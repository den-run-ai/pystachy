# == and != of Protocol values whose implementations are a dataclass's, a NamedTuple's and a plain
# class's objects: what @dataclass writes declines another class's object, a NamedTuple's object
# compares as a tuple, and objects that no method compares are equal only if they are one object
from dataclasses import dataclass
from typing import NamedTuple, Protocol


class Shape(Protocol):
    def area(self) -> float: ...


@dataclass
class Square:
    side: float

    def area(self) -> float:
        return self.side * self.side


@dataclass
class Rect:
    w: float
    h: float

    def area(self) -> float:
        return self.w * self.h


class Dot(NamedTuple):
    x: int
    y: int

    def area(self) -> float:
        return 0.0


class Blob:
    def area(self) -> float:
        return 1.0


def main() -> None:
    b = Blob()
    xs: list[Shape] = [Square(2.0), Square(2.0), Rect(2.0, 2.0), Dot(1, 2), Dot(1, 2), b, b, Blob()]
    for x in xs:
        print(" ".join([("=" if x == y else ".") + ("!" if x != y else ".") for y in xs]))
    print(xs[0] == Square(2.0), Square(2.0) == xs[1], xs[3] == (1, 2), (1, 2) == xs[3], xs[5] == b, xs[7] == b)
    print(xs[0] is None, xs[0] == None, None != xs[0])


main()
