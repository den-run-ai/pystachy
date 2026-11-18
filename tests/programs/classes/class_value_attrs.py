# A class object gives its class's attributes and calls its class methods and static methods
# (#7): k.attr is the class attribute of the class k is, which a class deriving from another
# may bind anew, and k.m(args) calls that class's m, a class method's cls being it. type(x).attr
# and x.__class__.m() read them through an object's class.
class Shape:
    sides = 0
    label = "shape"
    made = 0
    tags: list[str] = []

    def __init__(self, name: str = "s") -> None:
        self.name = name

    @classmethod
    def create(cls, name: str) -> "Shape":
        Shape.made += 1
        return cls(name.upper())

    @staticmethod
    def unit() -> float:
        return 1.0

    @classmethod
    def describe(cls) -> str:
        return cls.__name__ + ":" + cls.label + ":" + str(cls.sides)

    @classmethod
    def note(cls, text: str, times: int = 1) -> None:
        cls.tags.append(cls.__name__ + "=" + text * times)

    def area(self) -> float:
        return 0.0


class Square(Shape):
    sides = 4
    label = "square"

    @staticmethod
    def unit() -> float:
        return 4.0

    def area(self) -> float:
        return 16.0


class Circle(Shape):
    label = "circle"

    @classmethod
    def create(cls, name: str) -> "Shape":
        return cls("(" + name + ")")


def show(k: type[Shape]) -> None:
    o = k.create("x")
    k.note("n", times=2)
    print(k.sides, k.label, k.unit(), k.describe(), type(o).__name__, o.name, o.area(), k.made)


def effects(k: type[Shape], log: list[str]) -> str:
    # (the class object, then the arguments, then the call)
    def arg(s: str) -> str:
        log.append(s)
        return s

    return k.create(arg("a") + arg("b")).name


for kind in [Shape, Square, Circle]:
    show(kind)
k = Square
print(k.sides, k.create("q").name, type(Circle()).label, type(Square("z")).describe(), Shape.tags)


def of(o: Shape) -> str:
    return type(o).label + "/" + o.__class__.describe() + "/" + str(type(o).unit())


print(of(Shape()), of(Square()), of(Circle()))
seen: list[str] = []
print(effects(Circle, seen), effects(Square, seen), seen, Shape.made, Square.made)
maybe: type[Shape] | None = None
for step in range(2):
    try:
        print(maybe.label, maybe.describe())
    except AttributeError as e:
        print("AttributeError:", e)
    maybe = Circle
nothing: Shape | None = None
try:
    print(type(nothing).label)
except AttributeError as e:
    print("AttributeError:", e)
try:
    print(type(nothing).describe())
except AttributeError as e:
    print("AttributeError:", e)
order: list[str] = []


def side(s: str) -> str:
    order.append(s)
    return s


# (k.m is read before the arguments are evaluated: a missing one raises first)
for holder in [maybe, None]:
    try:
        holder.note(side("noted"), 1)
        print(Shape.tags[-1], order)
    except AttributeError as e:
        print("AttributeError:", e, order)
try:
    type(nothing).note(side("never"), 1)
except AttributeError as e:
    print("AttributeError:", e, order)
