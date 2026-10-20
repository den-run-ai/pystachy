class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def move(self, n: int) -> None:
        self.x += n


class Child(Point):
    __slots__ = ["z"]

    def __init__(self) -> None:
        super().__init__(2, 3)
        self.z = 4


class Open(Point):
    def __init__(self) -> None:
        super().__init__(5, 6)
        self.extra = 7


class Ordinary:
    def __init__(self) -> None:
        self.a = 8


class WithDict(Ordinary):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()
        self.b = 9


class Box:
    __slots__ = "value"

    def __init__(self, value):
        self.value = value


p = Point(1, 2)
p.move(2)
c = Child()
c.move(3)
o = Open()
w = WithDict()
print(p.x, p.y, c.x, c.y, c.z, o.extra, w.a, w.b)
print(Box(10).value, Box("ok").value)
