# A class with an ordinary primary base and several method-only secondary bases, and a subclass of
# such a hierarchy that adds another: a value typed by any base dispatches on its object's class,
# and isinstance() sees every base
class Shape:
    def __init__(self, name: str) -> None:
        self.name = name

    def area(self) -> float:
        return 0.0


class Describable:
    def describe(self) -> str:
        return "a shape"

    def shout(self) -> str:
        return self.describe().upper() + "!"


class Comparable:
    def key(self) -> float:
        return 0.0


class Square(Shape, Describable, Comparable):
    def __init__(self, side: float) -> None:
        self.name = "square"
        self.side = side

    def area(self) -> float:
        return self.side * self.side

    def describe(self) -> str:
        return "square " + str(self.side)

    def key(self) -> float:
        return self.area()


class Circle(Shape, Comparable):
    def __init__(self, r: float) -> None:
        self.name = "circle"
        self.r = r

    def key(self) -> float:
        return 3.0 * self.r * self.r


class Printable:
    def render(self) -> str:
        return "<shape>"


class Tile(Square, Printable):
    def render(self) -> str:
        return "[" + self.describe() + "]"


def total(xs: list[Comparable]) -> float:
    s = 0.0
    for x in xs:
        s += x.key()
    return s


def louder(d: Describable) -> str:
    return d.shout()


shapes: list[Shape] = [Square(2.0), Circle(1.0), Tile(3.0)]
print([s.name for s in shapes], [s.area() for s in shapes])
print(total([Square(2.0), Circle(1.0), Tile(1.0)]))
print(louder(Square(1.5)), louder(Tile(2.0)))
p: Printable = Tile(2.0)
print(p.render(), Printable().render())
print(isinstance(Tile(1.0), Describable), isinstance(Circle(1.0), Describable), isinstance(Tile(1.0), Printable), isinstance(Square(1.0), Printable))
