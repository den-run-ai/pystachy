# Unrelated classes that define a Protocol's methods share one list, field, dict and result.
from typing import Protocol


class Shape(Protocol):
    def area(self) -> float: ...

    def scaled(self, factor: float) -> "Shape": ...

    @property
    def label(self) -> str: ...


class Square:
    def __init__(self, side: float) -> None:
        self.side = side
        self.label = "square"

    def area(self) -> float:
        return self.side * self.side

    def scaled(self, factor: float) -> "Square":
        return Square(self.side * factor)


class Circle:
    def __init__(self, r: float) -> None:
        self.r = r

    def area(self) -> float:
        return 3.0 * self.r * self.r

    def scaled(self, factor: float) -> "Circle":
        return Circle(self.r * factor)

    @property
    def label(self) -> str:
        return "circle"


class Canvas:
    def __init__(self, first: Shape) -> None:
        self.current = first
        self.history: list[Shape] = [first]

    def replace(self, shape: Shape) -> None:
        self.current = shape
        self.history.append(shape)


def largest(shapes: list[Shape]) -> Shape:
    best = shapes[0]
    for s in shapes:
        if s.area() > best.area():
            best = s
    return best


def pick(round_one: bool) -> Shape:
    if round_one:
        return Circle(1.0)
    return Square(3.0)


shapes: list[Shape] = [Square(2.0), Circle(1.0), Square(1.5)]
print([(s.label, s.area()) for s in shapes])
print(largest(shapes).label, sum(s.area() for s in shapes))
grown = [s.scaled(2.0) for s in shapes]
print([g.area() for g in grown])
canvas = Canvas(Square(1.0))
canvas.replace(Circle(2.0))
print(canvas.current.label, [s.label for s in canvas.history])
print(pick(True).area(), pick(False).label)
by_name: dict[str, Shape] = {"a": Circle(3.0), "b": Square(4.0)}
for name in sorted(by_name):
    print(name, by_name[name].area())
