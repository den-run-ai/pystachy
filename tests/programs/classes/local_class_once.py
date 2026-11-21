# Classes defined in the body of functions that run at most once (one call, by the module's code or
# by such a function, outside loops): CPython makes one class object, which the module makes here,
# with CPython's __qualname__ (report.<locals>.Square), reprs, bases, methods, forward references,
# class values and isinstance(); a NamedTuple and a generator's class too
from typing import NamedTuple


class Shape:
    def area(self) -> float:
        return 0.0


def report() -> None:
    class Square(Shape):
        sides = 4

        def __init__(self, s: float) -> None:
            self.s = s

        def area(self) -> float:
            return self.s * self.s

        def doubled(self) -> "Square":
            return Square(self.s * 2)

        @staticmethod
        def unit() -> "Square":
            return Square(1.0)

        @classmethod
        def named(cls) -> str:
            return cls.__name__

        @property
        def side(self) -> float:
            return self.s

    class Tagged(Square):
        def area(self) -> float:
            return super().area() + 1

    class Pair(NamedTuple):
        a: int
        b: int

    class Key:
        def __init__(self, k: int) -> None:
            self.k = k

        def __eq__(self, other: object) -> bool:
            return isinstance(other, Key) and other.k == self.k

        def __hash__(self) -> int:
            return hash(self.k)

    sq = Square(3.0)
    shapes: list[Shape] = [sq, Tagged(2.0), Shape()]
    print([s.area() for s in shapes], sq.doubled().side, Square.unit().area(), Square.named(), Square.sides)
    print(isinstance(sq, Square), isinstance(Tagged(1.0), Square), type(sq) is Square, type(sq).__qualname__)
    make = Square
    print(make(5.0).area(), Pair(1, 2), Pair(1, 2)._replace(b=5), Pair._fields)
    keys = {Key(1), Key(1), Key(2)}
    print(len(keys), Key(3) == Key(3), Key(3) in keys)
    area_of = lambda n: Square(n).area()
    print(area_of(4.0), sorted([Square(x).area() for x in [3.0, 1.0]]))

    def helper() -> float:
        return Tagged(5.0).area()

    print(helper())


def numbers():
    class Counter:
        def __init__(self) -> None:
            self.n = 0

        def bump(self) -> int:
            self.n += 1
            return self.n

    c = Counter()
    yield c.bump()
    yield c.bump()


def main() -> None:
    report()
    print(list(numbers()))


if __name__ == "__main__":
    main()
