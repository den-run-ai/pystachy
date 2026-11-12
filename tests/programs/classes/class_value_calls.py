# A call of a class object makes an object of the class it is, with that class's constructor
# (#7). CPython evaluates the class object, then the arguments, once and in order, then calls;
# a class object that is None raises TypeError after the arguments
import abc
from dataclasses import dataclass
from typing import Callable, Iterator, NamedTuple


class Shape:
    def __init__(self, name: str, sides: int = 0) -> None:
        self.name = name
        self.sides = sides

    def area(self) -> float:
        return 0.0

    def describe(self) -> str:
        return f"{type(self).__name__}({self.name!r}, {self.sides}) area={self.area():.2f}"


class Square(Shape):
    def __init__(self, name: str, sides: int = 4) -> None:
        super().__init__(name, sides)
        self.side = 2.0

    def area(self) -> float:
        return self.side * self.side


class Circle(Shape):
    def area(self) -> float:
        return 3.0


class Task(abc.ABC):
    @abc.abstractmethod
    def run(self) -> int:
        ...


class Five(Task):
    def run(self) -> int:
        return 5


@dataclass
class Point:
    x: int = 1
    y: int = 2


@dataclass
class Point3(Point):
    z: int = 3


class Pair(NamedTuple):
    a: int
    b: str


def note(tag: str) -> str:
    print("evaluating", tag)
    return tag


def pick(i: int) -> type[Shape]:
    print("picking", i)
    return [Shape, Square, Circle][i % 3]


def build(kind: type[Shape], name: str) -> Shape:
    return kind(name)


def run(kind: type[Task]) -> str:
    try:
        return str(kind().run())
    except TypeError as e:
        return "TypeError: " + str(e)


def call(kind: type[Shape] | None) -> str:
    try:
        return kind(note("argument")).describe()
    except TypeError as e:
        return "TypeError: " + str(e)


def applier(kind: type[Shape]) -> Callable[[str], float]:
    def apply(name: str) -> float:
        return kind(name).area()
    return apply


def make(kind, name: str):
    # (a template: compiled for each class object's type it is called with)
    return kind(name)


def split(flag: bool) -> tuple[type[Shape], type[Shape]]:
    return (Square, Circle) if flag else (Circle, Shape)


def kinds_of(xs: list[Shape]) -> Iterator[type[Shape]]:
    for x in xs:
        yield type(x)


for i in range(4):
    s = pick(i)(note("n" + str(i)), sides=i)
    print(s.describe())
print(build(Square, "sq").describe(), build(Circle, "c").describe(), build(Shape, "s").describe())
kinds: list[type[Shape]] = [Circle, Square, Shape, Square]
made = [k("x" + str(j)) for j, k in enumerate(kinds)]
print([m.describe() for m in made])
print([type(m).__name__ for m in made], [type(m) is Square for m in made])
again = [type(m)(m.name + "'") for m in made]
print([a.describe() for a in again], [k.__name__ for k in kinds_of(again)])
table: dict[str, type[Shape]] = {"square": Square, "circle": Circle}
for key in sorted(table):
    print(key, table[key].__name__, table[key](key).area(), applier(table[key])(key))
print(call(Circle), "|", call(None))
print(run(Five), "|", run(Task))
pts: list[type[Point]] = [Point, Point3]
print([p() for p in pts], [p.__name__ for p in pts], pts[1](5, 6), type(Point3()) is pts[1], pts[0](y=9))
pk: type[Pair] = Pair
print(pk(1, "x"), pk.__name__, type(pk(2, "y")) is Pair)
for kind, n in [(Square, "a"), (Circle, "b")]:
    print(kind.__name__, kind(n).area())

print(make(Square, "t").describe(), make(Circle, "u").describe(), "-")
first, second = split(True)
print(first.__name__, second("z").area(), [k.__name__ for k in split(False)])
pick_kind = lambda i: [Square, Circle][i]  # noqa: E731
print(pick_kind(0)("l").area(), pick_kind(1).__name__)
lookup = {c.__name__: c for c in [Square, Circle, Shape]}
print(sorted(lookup), lookup["Circle"]("d").area())
for each in (Square, Circle, Shape):
    print(each.__name__, each("e").area(), each in (Square, Shape), issubclass(each, Square))
print([type(o).__name__ for o in [k("f") for k in (Circle, Square, Circle)]])
