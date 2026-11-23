# isinstance() of a Protocol value tests its object's class (a hierarchy's by the object's own
# class), and narrows a local, parameter or attribute to that class where it holds: in if and
# elif, after an early return, in and, and in a conditional expression.
from typing import Protocol


class Shape(Protocol):
    def area(self) -> float: ...


class Square:
    def __init__(self, side: float) -> None:
        self.side = side

    def area(self) -> float:
        return self.side * self.side


class Circle:
    def __init__(self, r: float) -> None:
        self.r = r

    def area(self) -> float:
        return 3.0 * self.r * self.r


class Base:
    def area(self) -> float:
        return 1.0


class Derived(Base):
    def __init__(self, extra: int) -> None:
        self.extra = extra

    def area(self) -> float:
        return 2.0


def describe(s: Shape) -> str:
    if isinstance(s, Square):
        return f"square {s.side}"
    elif isinstance(s, Circle):
        return f"circle {s.r}"
    if isinstance(s, Derived):
        return f"derived {s.extra}"
    if isinstance(s, Base):
        return "base"
    return "other"


def radius(x: Shape) -> float:
    if not isinstance(x, Circle):
        return -1.0
    x.r += 1.0
    return x.r


def big(x: Shape | None) -> bool:
    return isinstance(x, Square) and x.side > 1.0


def side(x: Shape) -> float:
    return x.side if isinstance(x, Square) else 0.0


class Holder:
    # (an attribute narrows as a local does, until something may store it)
    def __init__(self, shape: Shape) -> None:
        self.shape = shape

    def side(self) -> float:
        if isinstance(self.shape, Square):
            return self.shape.side
        return -1.0

    def swap(self) -> float:
        if isinstance(self.shape, Square):
            s = self.shape.side
            self.shape = Circle(s)
            return self.shape.area()
        return 0.0


b: Base = Derived(7)
shapes: list[Shape] = [Square(2.0), Circle(1.0), b, Base(), Derived(3)]
for s in shapes:
    print(describe(s), isinstance(s, (Square, Circle)), isinstance(s, Base), isinstance(s, Square | Derived), isinstance(s, object))
none: Shape | None = None
print(isinstance(none, Square), isinstance(none, object), big(none), big(shapes[0]), big(Square(0.5)))
c = Circle(5.0)
print(radius(c), radius(Square(1.0)), c.r, side(shapes[0]), side(shapes[1]))
h = Holder(Square(3.0))
print(h.side(), Holder(c).side(), h.swap(), h.side(), h.swap())
