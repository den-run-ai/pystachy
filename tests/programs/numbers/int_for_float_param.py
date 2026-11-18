# An int or a bool where a parameter is annotated float (#711): PEP 484 accepts it and CPython
# passes the object on, so the function or method is compiled again for it, as a template with
# an unannotated parameter is. The int stays an int: in isinstance(), repr(), a result that
# returns it and the arithmetic of ints.
from dataclasses import dataclass


def half(x: float) -> float:
    return x / 2


def scale(x: float, k: float = 2.0) -> float:
    x = x * k
    return x


def describe(x: float) -> str:
    if isinstance(x, int):
        return f"int {x!r}"
    return f"float {x!r}"


def hyp(a: float, b: float) -> float:
    return (a * a + b * b) ** 0.5


def fact(x: float) -> float:
    if x <= 1:
        return 1.0
    return x * fact(x - 1)


def fact_one(x: float) -> float:
    return 1.0 if x <= 1 else x * fact_one(x - 1)


def ident(x: float) -> float:
    return x


def clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def pick(x: float, flag: bool) -> float:
    if flag:
        return x
    return 0.5


def floor_half(x: float) -> float:
    return x // 2


def adder(x: float) -> float:
    add = lambda y: x + y
    return sum([add(i) for i in range(3)])


def show(x: float) -> None:
    print(x, type(x).__name__, repr(x))


def trace(tag: str, v: int) -> int:
    print("eval", tag)
    return v


class Acc:
    def __init__(self) -> None:
        self.total = 0.0

    def add(self, x: float) -> None:
        self.total += x

    def scaled(self, k: float) -> float:
        return self.total * k

    def keep(self, x: float) -> float:
        return x


@dataclass
class Vec:
    x: float
    y: float

    def scale(self, k: float) -> "Vec":
        return Vec(self.x * k, self.y * k)

    def dot(self, ox: float, oy: float) -> float:
        return self.x * ox + self.y * oy


n = 3
print(half(3), half(3.0), half(n), half(True), half(x=7))
print(scale(3), scale(3, 2.5), scale(k=4, x=1.5), scale(2, k=3))
print(describe(3), describe(3.0), describe(False))
print(hyp(3, 4), hyp(3.0, 4), hyp(3, 4.0))
print(fact(5), fact(5.0), fact_one(5), fact_one(5.0))
print(ident(3), ident(3.5), repr(ident(True)))
print(clamp(5, 0, 3), clamp(5, 0.0, 3.5), clamp(1, 0.5, 3))
print(pick(3, True), pick(3, False), pick(3.0, True))
print(floor_half(7), floor_half(7.0), 2**62 + ident(2**62 - 1))
print(adder(1), adder(1.5))
show(2)
show(2.0)
show(len("abc"))
print(hyp(trace("a", 3), trace("b", 4)), hyp(b=trace("b", 4), a=trace("a", 3)))
v = ident(4)
print(v + 1, type(v).__name__, [half(i) for i in range(3)])
w = pick(2, len("ab") == 2)
print(w, type(w).__name__)

acc = Acc()
acc.add(2)
acc.add(0.5)
acc.add(True)
print(acc.total, acc.scaled(2), acc.scaled(1.5), acc.keep(7), acc.keep(7.0), Acc.scaled(acc, 3))
vec = Vec(1.5, 2.0).scale(2)
print(vec, vec.dot(1, 2), Vec(1.0, 1.0).dot(m := 3, 0.5), m)
