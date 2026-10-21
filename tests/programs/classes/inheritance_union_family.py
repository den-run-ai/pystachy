# An annotation's union of a class and classes derived from it (datetime | date, Square | Shape)
# is that class, whose type holds their objects too: calls run each object's own methods and
# isinstance() narrows to a derived class, as with CPython's objects
from datetime import date, datetime
from typing import Optional, Union


class Shape:
    def __init__(self, name: str) -> None:
        self.name = name

    def area(self) -> float:
        return 0.0


class Square(Shape):
    def __init__(self, side: float) -> None:
        super().__init__("square")
        self.side = side

    def area(self) -> float:
        return self.side * self.side


class Unit(Square):
    def __init__(self) -> None:
        super().__init__(1.0)
        self.name = "unit"


def make(k: int) -> Square | Shape | Unit:
    if k == 0:
        return Shape("point")
    if k == 1:
        return Square(2.0)
    return Unit()


def describe(s: Shape | Square | None) -> str:
    if s is None:
        return "nothing"
    if isinstance(s, Square):
        return f"{s.name} side {s.side} area {s.area()}"
    return f"{s.name} area {s.area()}"


for k in range(3):
    print(describe(make(k)), type(make(k)).__name__)
print(describe(None))
shapes: list[Union[Shape, Unit]] = [make(2), make(0)]
print([s.area() for s in shapes])


def when(full: bool) -> datetime | date:
    if full:
        return datetime(2020, 1, 2, 3, 4)
    return date(2020, 1, 2)


def maybe(k: int) -> Optional[Union[date, datetime]]:
    if k == 0:
        return None
    return when(k == 2)


def show(k: int) -> None:
    v = when(k == 1)
    print(v, repr(v), type(v).__name__, isinstance(v, datetime), v.year, maybe(k))
    if isinstance(v, datetime):
        print("hour", v.hour)


for k in range(3):
    show(k)
xs: list[date | datetime] = [when(True), when(False)]
print(xs, sorted([when(False), date(2019, 5, 5)]))
print(when(True) == datetime(2020, 1, 2, 3, 4), when(False) == date(2020, 1, 2), when(True) == when(False))
