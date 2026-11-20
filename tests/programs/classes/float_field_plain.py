# Fields of plain classes annotated float that are given ints (#1534): a store in a method, a
# class-body default, a class attribute assigned through the class, and a constructor's int
# argument for a float parameter that fills a field (also of a class whose body annotates all
# its fields: a fixed layout, and in a hierarchy). The field holds an int | float.
class Counter:
    step: float = 1
    bias: float = 0.5

    def __init__(self) -> None:
        self.total: float = 0
        self.last: float = 1.5
        self.n = 0

    def add(self, v: float) -> None:
        self.total += v * self.step
        self.last = v
        self.n += 1

    def reset(self) -> None:
        self.total = 0
        self.last = 0

    def mean(self) -> float:
        return self.total / self.n if self.n else 0.0


class Point:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y: float = y
        self.norm1: float = abs(x) + abs(y)

    def show(self) -> str:
        return f"{type(self).__name__}({self.x!r}, {self.y!r}) {self.norm1!r}"


class Point3(Point):
    def __init__(self, x: float, y: float, z: float) -> None:
        super().__init__(x, y)
        self.z: float = z

    def show(self) -> str:
        return f"Point3({self.x!r}, {self.y!r}, {self.z!r})"


class Fixed:
    x: float
    y: float

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


class Slotted:
    __slots__ = ("lo", "hi")

    def __init__(self) -> None:
        self.lo: float = 0
        self.hi: float = 1.5


class Failure(Exception):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.cost: float = 0


c = Counter()
print(c.total, c.last, c.n, c.mean(), isinstance(c.total, int), Counter.step, c.step, Counter.bias)
c.add(2.5)
print(c.total, c.last, c.mean(), isinstance(c.total, int))
c.reset()
print(c.total, c.last, isinstance(c.total, int), isinstance(c.last, int))
c.add(2.5)
c.add(1.5)
print(c.total, c.last, c.mean())
Counter.step = 3
c.add(0.5)
print(c.total, Counter.step, c.step, Counter().step)
Counter.step = 0.5
c.step = 4
print(Counter.step, c.step, Counter().step)

pts: list[Point] = [Point(1, 2), Point(1.5, 2), Point3(1, 2.5, 3), Point3(0.5, 0.25, 0.125), Point(-1.0, 2.0)]
for pt in pts:
    print(pt.show(), pt.x + pt.y, isinstance(pt.x, int), isinstance(pt.y, int))

f1 = Fixed(1, 2)
f2 = Fixed(1.5, 2)
print(f1.x, f1.y, f2.x, f2.y, f1.x + f2.x, isinstance(f1.x, int), isinstance(f2.x, int))

s = Slotted()
s.hi = 3
print(s.lo, s.hi, s.lo + s.hi, isinstance(s.lo, int))

try:
    e = Failure("boom")
    e.cost = 3
    raise e
except Failure as caught:
    print(caught, caught.cost, caught.cost / 2)
