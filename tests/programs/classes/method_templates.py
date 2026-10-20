# A method whose parameters (but self, or a class method's cls) have no annotations is a
# template, as a module-level function is: each call compiles it for its argument types
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def add(self, x):
        return self.v + x

    def pair(self, a, b=None, *, sep="/"):
        return (a, b, sep)

    def total(self, *xs):
        return self.v + sum(xs)

    def names(self, **kw):
        return sorted(kw)

    def forward(self, *args, **kw):
        return self.pair(*args, **kw)

    @staticmethod
    def twice(x):
        return x * 2

    @classmethod
    def make(cls, v):
        return cls(v * 10)

    def fact(self, k):
        if k <= 1:
            return 1
        return k * self.fact(k - 1)

    def even(self, n) -> bool:
        return True if n == 0 else self.odd(n - 1)

    def odd(self, n) -> bool:
        return False if n == 0 else self.even(n - 1)

    def maybe(self, flag):
        if flag:
            return self
        return None

    def show(self, x):
        if isinstance(x, str):
            return "str " + x
        if isinstance(x, Box):
            return "box " + str(x.v)
        return "other " + str(x)

    def keyed(self, x):
        return -x

    def adder(self, k):
        return lambda y: y + k + self.v

    def __add__(self, other):
        return Box(self.v + other.v)

    def __mul__(self, k):
        return Box(self.v * k)

    def __call__(self, s, i):
        return s[i:]

    def __repr__(self) -> str:
        return f"Box({self.v})"


b = Box(3)
print(b.add(4), b.add(0.5), b.add(True))
print(b.pair(1), b.pair("x", [1]), b.pair(1, 2, sep="-"), b.pair(b=4, a=5))
print(b.total(), b.total(1, 2, 3), b.total(0.5))
print(b.names(), b.names(a=1, c="x"), b.forward(1, sep=":"), b.forward("p", "q"))
print(Box.twice(4), Box.twice("ab"), b.twice(1.5), Box.make(2), b.make(1))
print(b.fact(5), b.fact(1), b.even(10), b.odd(7), b.maybe(True), b.maybe(False))
print(b.show("s"), b.show(b), b.show(2.5), b.show([1]))
print(b + Box(5), b * 3, b("hello", 2), b([1, 2, 3], 1))

# bound template methods as values: each call through one compiles its instance
f = b.add
print(f(10), f(2.5), sorted([3, 1, 2], key=b.keyed), list(map(b.keyed, [1, 2])))
g: Callable[[int], int] = b.add
h: Callable[[str], str] = b.show
print(g(1), h("z"), b.adder(10)(5), [b.adder(i)(1) for i in range(3)])


class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        return self.n == other.n

    def __lt__(self, other):
        return self.n < other.n

    def __getitem__(self, i):
        return self.n * i

    def __contains__(self, x):
        return x == self.n

    def __repr__(self) -> str:
        return f"V({self.n})"


a = V(2)
print(a == V(2), a != V(3), a < V(5), V(5) < a, sorted([V(5), a, V(3)]), max([a, V(9), V(4)]))
print(V(3) in [a, V(3)], [a, V(3)].index(V(3)), [V(1), V(1)].count(V(1)), [a] == [V(2)])
print(a[3], a[1.5], 2 in a, 3 in a)


@dataclass
class Pt:
    x: int
    y: int

    def moved(self, dx, dy=0):
        return Pt(self.x + dx, self.y + dy)


p = Pt(1, 2)
print(p.moved(3), p.moved(1, dy=5), p.moved(-1).moved(-1))


class Shape:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h

    def area_of(self, other):
        return other.w * other.h

    def setw(self, v):
        self.w = v
        return self


s = Shape(2, 3)
print(s.area_of(s), s.area_of(Shape(4, 5)), s.setw(7).w, s.w)


class Oops(ValueError):
    def detail(self, extra):
        return str(self) + "/" + str(extra)


class Worse(Oops):
    pass


try:
    raise Worse("bad")
except Oops as e:
    print(e.detail(1), e.detail("x"), type(e).__name__)
print(Oops("o").detail(2.0))


# a method whose annotations mention a TypeVar (or its own PEP 695 type parameter) is a template
class Shelf:
    def __init__(self, n: int) -> None:
        self.n = n

    def first(self, xs: list[T]) -> T:
        return xs[0]

    def both(self, a: T, b: T) -> list[T]:
        return [a, b] * self.n

    def same[U](self, u: U) -> U:
        return u


sh = Shelf(2)
print(sh.first([3, 4]), sh.first(["a"]), sh.both(1, 2), sh.both("x", "y"), sh.same(1.5), sh.same(sh).n)
