# Subclasses of a class that functools.total_ordering and cached_property changed: the methods
# added call the object's own class's method, and an object of a subclass keeps the values.
from functools import cached_property, total_ordering


@total_ordering
class Size:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        if not isinstance(other, Size):
            return NotImplemented
        return self.key() == other.key()

    def __lt__(self, other):
        print("Size.__lt__")
        if not isinstance(other, Size):
            return NotImplemented
        return self.key() < other.key()

    def key(self) -> int:
        return self.n


class Reversed(Size):
    # the methods total_ordering wrote for Size call type(self)'s __lt__: this one
    def __lt__(self, other):
        print("Reversed.__lt__")
        if not isinstance(other, Size):
            return NotImplemented
        return self.key() > other.key()


class Doubled(Size):
    def key(self) -> int:
        return self.n * 2


class Shape:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h
        self.calls = 0

    @cached_property
    def area(self) -> int:
        self.calls += 1
        return self.w * self.h


class Square(Shape):
    def __init__(self, w: int) -> None:
        super().__init__(w, w)

    @cached_property
    def diagonal2(self) -> int:
        self.calls += 1
        return 2 * self.area


xs: list[Size] = [Size(3), Reversed(1), Doubled(2), Reversed(5)]
for a in xs:
    print([a < b for b in xs], [a >= b for b in xs], [a > b for b in xs], [a <= b for b in xs])
s = Square(3)
print(s.diagonal2, s.area, s.diagonal2, s.calls)
shapes: list[Shape] = [Shape(2, 3), s]
print([x.area for x in shapes], [x.calls for x in shapes])
