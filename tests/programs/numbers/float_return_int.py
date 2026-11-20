# A function annotated -> float that returns an int (#1534): CPython returns the int, so the
# function returns an int | float, as if annotated so. Functions, methods, a property, static
# and class methods, overrides in a hierarchy (which then all return the union) and recursion.
from abc import ABC, abstractmethod


def zero() -> float:
    return 0


def pick(flag: bool) -> float:
    if flag:
        return 1
    return 2.5


def clamp(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def tri(n: int) -> float:
    if n == 0:
        return 0
    return n + tri(n - 1)


def geo(n: int) -> float:
    if n == 0:
        return 1
    return geo(n - 1) / 2


class Temp:
    def __init__(self) -> None:
        self._c: float = 0

    @property
    def c(self) -> float:
        return self._c

    @c.setter
    def c(self, v: float) -> None:
        self._c = v

    @staticmethod
    def unit() -> float:
        return 1

    @classmethod
    def base(cls) -> float:
        return 0

    def chain(self) -> float:
        return self.twice() + 1

    def twice(self) -> float:
        return self.c * 2


class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...

    def twice(self) -> float:
        return self.area() * 2


class Square(Shape):
    def __init__(self, s: float) -> None:
        self.s: float = s

    def area(self) -> float:
        return self.s * self.s


class Circle(Shape):
    def area(self) -> float:
        return 3.5


print(zero(), pick(True), pick(False), zero() + 1, pick(True) / 2, isinstance(zero(), int), isinstance(pick(False), float))
print(clamp(5, 0, 3), clamp(1.5, 0, 3), clamp(-1.0, 0, 3), tri(4), geo(0), geo(3))
t = Temp()
print(t.c, Temp.unit(), Temp.base(), t.c + Temp.unit(), t.twice(), t.chain(), isinstance(t.chain(), int))
t.c = 2.5
print(t.c, t.twice(), t.chain(), isinstance(t.chain(), int))
shapes: list[Shape] = [Square(2), Square(1.5), Circle()]
for s in shapes:
    print(s.area(), s.twice(), isinstance(s.area(), int))
print(sum(s.area() for s in shapes))
