# pystachy: dynamic-any
# Keyword arguments through Any values (#774): a method of the program's classes, a function
# value, a closure, a bound method, an object's __call__ and a field that holds a function each
# bind them to their own parameters, as CPython does; list.sort() and dict.update() take theirs
# as typed code does.
from typing import Any


class Shape:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h

    def scaled(self, k: int, plus: int = 0) -> int:
        return self.w * self.h * k + plus

    def label(self, *, unit: str, sep: str = " ") -> str:
        return str(self.w * self.h) + sep + unit

    @staticmethod
    def area(w: int, h: int = 1) -> int:
        return w * h

    @classmethod
    def unit(cls, side: int, name: str = "square") -> str:
        return name + ":" + str(side)


class Other:
    def scaled(self, plus: int, k: int = 1) -> int:
        return plus * 100 + k


def g(a: int, b: int = 0) -> int:
    return a + b * 10


class Adder:
    def __init__(self, base: int) -> None:
        self.base = base

    def __call__(self, x: int, y: int = 0) -> int:
        return self.base + x + y


class Holder:
    def __init__(self) -> None:
        self.fn: Any = g


def make(n: int) -> Any:
    def add(x: int, y: int = 1) -> int:
        return n + x + y

    return add


x: Any = Shape(2, 3)
print(x.scaled(2, plus=1), x.scaled(k=3), x.scaled(plus=5, k=1))
print(x.label(unit="cm"), x.label(sep="-", unit="m"))
print(x.area(w=4), x.area(2, h=5), x.unit(side=3), x.unit(2, name="cube"))
for o in [Shape(1, 1), Other()]:
    y: Any = o
    print(y.scaled(k=2, plus=5))
    try:
        print(y.scaled(3, k=2))
    except TypeError as e:
        print("TypeError:", e)
f: Any = g
print(f(1, b=2), f(b=3, a=4), f(a=5))
add: Any = make(10)
print(add(1, y=5), add(x=2))
bm: Any = x.scaled
print(bm(k=2, plus=7))
c: Any = Adder(100)
print(c(1, y=2), c(x=3))
h: Any = Holder()
print(h.fn(1, b=4))
xs: Any = [{"n": 2}, {"n": 1}, {"n": 3}]
xs.sort(key=lambda r: r["n"], reverse=True)
print(xs)
xs.sort(key=lambda r: r["n"])
print(xs)
d: Any = {"a": 1}
d.update(b=2, c=[3])
d.update({"z": 0}, a=9)
print(d)
