# A subclass can override a static or class method with one of the same kind. Calls through
# a class name use that class's method, and an inherited class method's cls.m() calls the
# method of the class it was called through.


class Shape:
    sides = 0

    def __init__(self, name: str, size: int) -> None:
        self.name = name
        self.size = size

    @classmethod
    def parse(cls, text: str):
        name, size = text.split(":")
        return cls(name, int(size))

    @classmethod
    def unit(cls):
        return cls.parse("unit:1")

    @classmethod
    def kind(cls) -> str:
        return "shape with %d sides" % cls.sides

    @staticmethod
    def scale(n: int) -> int:
        return n * 2

    @classmethod
    def doubled(cls, n: int) -> int:
        return cls.scale(n)

    def describe(self) -> str:
        return "%s %s(%d)" % (type_name(self), self.name, self.size)


class Square(Shape):
    sides = 4

    @classmethod
    def parse(cls, text: str):
        print("Square.parse", text)
        return cls(text.upper(), len(text))

    @staticmethod
    def scale(n: int) -> int:
        return n * 4


class Cube(Square):
    @classmethod
    def kind(cls) -> str:
        return "solid of squares"


def type_name(s: Shape) -> str:
    if isinstance(s, Cube):
        return "Cube"
    if isinstance(s, Square):
        return "Square"
    return "Shape"


print(Shape.parse("a:3").describe(), Square.parse("ab").describe(), Cube.parse("xyz").describe())
print(Shape.unit().describe(), Square.unit().describe(), Cube.unit().describe())
print(Shape.kind(), "|", Square.kind(), "|", Cube.kind())
print(Shape.scale(5), Square.scale(5), Cube.scale(5))
print(Shape.doubled(3), Square.doubled(3), Cube.doubled(3))

shapes: list[Shape] = [Shape.parse("s:2"), Square.unit(), Cube.parse("q")]
for s in shapes:
    print(s.describe(), s.sides)
