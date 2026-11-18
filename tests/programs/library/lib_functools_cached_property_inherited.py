# A cached_property read through a subclass, and one that a subclass adds and that reads the
# base class's: each object keeps its own values.
from functools import cached_property


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


s = Square(3)
print(s.diagonal2, s.area, s.diagonal2, s.calls)
shapes: list[Shape] = [Shape(2, 3), s, Square(4)]
print([x.area for x in shapes], [x.calls for x in shapes])
shapes[0].w = 10
del shapes[0].area
print([x.area for x in shapes], [x.calls for x in shapes])
