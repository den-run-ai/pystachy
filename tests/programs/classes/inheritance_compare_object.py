# Comparison methods that take the other operand as a template's parameter (other: object, or
# no annotation) are compiled once for each class of the object they are called on, with other
# as the type the comparison declares it (#625), so each must still see the other operand's own
# class: what isinstance() and type() say of it, a subclass's field read behind isinstance(),
# a subclass's override (whose reflected method goes first), and None on either side; also
# where a list's search compares (identical items match without __eq__), and through Any.
from typing import Any


class Shape:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        print("  Shape.__eq__", self.name, type(other).__name__, isinstance(other, Square))
        if isinstance(other, Square):
            return self.name == other.name and other.side > 1
        return isinstance(other, Shape) and self.name == other.name

    def __lt__(self, other) -> bool:
        print("  Shape.__lt__", self.name, type(other).__name__)
        return other is not None and self.name < other.name


class Square(Shape):
    def __init__(self, name: str, side: int) -> None:
        super().__init__(name)
        self.side = side

    def __eq__(self, other: object) -> bool:
        print("  Square.__eq__", self.name, type(other).__name__)
        return isinstance(other, Square) and self.side == other.side


class Circle(Shape):
    pass


class Dot(Circle):
    def __lt__(self, other) -> bool:
        print("  Dot.__lt__", self.name, type(other).__name__)
        return other is not None and len(self.name) < len(other.name)


def eq(a: Shape | None, b: Shape | None) -> bool:
    return a == b


def ne(a: Shape | None, b: Shape | None) -> bool:
    return a != b


def lt(a: Shape | None, b: Shape | None) -> bool:
    return a < b


def gt(a: Shape | None, b: Shape | None) -> bool:
    return a > b


def label(x: Shape | None) -> str:
    return type(x).__name__ + " " + x.name if x is not None else "None"


xs: list[Shape | None] = [None, Shape("a"), Square("a", 2), Circle("a"), Dot("bb"), Square("b", 1)]
for x in xs:
    for y in xs:
        print(label(x), "|", label(y))
        print(" ==", eq(x, y))
        print(" !=", ne(x, y))
        try:
            print(" <", lt(x, y))
        except TypeError as e:
            print(" < TypeError:", e)
        try:
            print(" >", gt(x, y))
        except TypeError as e:
            print(" > TypeError:", e)


def circles(a: Circle, b: Circle) -> bool:
    # (operands of a subclass: other is a Circle there)
    return a == b and not a < b


print(circles(Circle("c"), Dot("c")), circles(Dot("c"), Circle("c")))


def same(a: Any, b: Any) -> bool:
    return a == b


shapes: list[Shape] = [Shape("a"), Square("a", 2), Circle("a"), Dot("bb")]
for s in shapes:
    print(label(s), "in:", s in shapes)
    print(label(s), "index:", shapes.index(s))
    print(label(s), "count:", shapes.count(s))
print(same(Square("a", 2), Shape("a")), same(Shape("a"), Circle("a")), same(Dot("bb"), None))
