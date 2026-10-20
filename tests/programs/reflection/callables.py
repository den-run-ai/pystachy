# Callable[[A, B], R] annotations: a function value (a def, a builtin, a lambda, a closure) becomes
# a Callable where one is expected, so one variable, field, list or dict holds different functions
import math
from collections.abc import Callable as AbcCallable
from dataclasses import dataclass
from typing import Callable, Optional


def double(x: int) -> int:
    return x * 2


def triple(x):
    return x * 3


def shout(s: str) -> None:
    print(s.upper())


def apply_all(fs: list[Callable[[int], int]], x: int) -> list[int]:
    return [f(x) for f in fs]


def adder(n: int) -> Callable[[int], int]:
    return lambda x: x + n


def compose(f: Callable[[int], int], g: Callable[[int], int]) -> Callable[[int], int]:
    return lambda x: f(g(x))


class Parser:
    def __init__(self, fn: Callable[[str, int], int]) -> None:
        self.fn = fn

    def __call__(self, s: str, i: int) -> int:
        return self.fn(s, i)

    def then(self, other: "Parser") -> "Parser":
        def both(s: str, i: int) -> int:
            j = self(s, i)
            return other(s, j) if j >= 0 else -1
        return Parser(both)


def lit(c: str) -> Parser:
    return Parser(lambda s, i: i + 1 if i < len(s) and s[i] == c else -1)


@dataclass
class Op:
    name: str
    run: Callable[[float, float], float]


class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def scaler(self) -> Callable[[int], int]:
        return lambda x: x * self.k


def table() -> dict[str, Callable[[float], float]]:
    return {"sqrt": math.sqrt, "neg": lambda v: -v, "half": lambda v: v / 2}


def maybe(f: Optional[Callable[[int], int]], x: int) -> int:
    return x if f is None else f(x)


def run_template(f, x):
    return f(x)


def raising(x: int) -> int:
    if x < 0:
        raise ValueError(f"negative {x}")
    return x


fs: list[Callable[[int], int]] = [double, triple, lambda v: v - 1, abs, adder(10)]
print(apply_all(fs, 5), apply_all([double], -7), compose(double, adder(1))(5), compose(adder(1), double)(5))
p = lit("a").then(lit("b")).then(lit("c"))
print(p("abc", 0), p("abx", 0), lit("x")("x", 0), lit("x")("y", 0))
ops = [Op("add", lambda a, b: a + b), Op("pow", math.pow), Op("max", max)]
print([(o.name, o.run(2.0, 3.0)) for o in ops])
print(Scale(4).scaler()(5), [(k, f(16.0)) for k, f in sorted(table().items(), key=lambda kv: kv[0])])
print(maybe(None, 3), maybe(double, 3), maybe(lambda v: v * v, 3), run_template(adder(5), 1))
g: Callable[[int], int] = double
print(g(4), g == double, g == triple)
g = triple
print(g(4), g == double)
h: AbcCallable[[str], None] = shout
h("quiet")
h = print
h("printed")
noargs: Callable[[], str] = lambda: "none"
print(noargs(), (double, triple)[1](2))
safe: Callable[[int], int] = raising
for v in [3, -2]:
    try:
        print(safe(v))
    except ValueError as e:
        print("caught", e)
same = adder(1)
c1: Callable[[int], int] = same
c2: Callable[[int], int] = same
c3: Callable[[int], int] = adder(1)
print(c1 == c2, c1 is c2, c1 == c3, c1 != c3)


def side(x: int) -> int:
    print("side", x)
    return x


def neg(x: int) -> int:
    return -x


# a Callable that is None raises once its arguments are evaluated
none_f: Callable[[int], int] | None = None
try:
    none_f(side(3))
except TypeError as e:
    print("TypeError:", e)
# Callables that may be None compare as CPython's functions and None do
o1: Callable[[int], int] | None = double
o2: Optional[Callable[[int], int]] = double
o3: Callable[[int], int] | None = None
o4: Callable[[int], int] | None = same
o5: Callable[[int], int] | None = same
print(o1 == o2, o1 is o2, o1 != o3, o3 == o3, o3 is None, o1 == double, o4 is o5, o4 == o1, c1 == o4)
# a Callable as the key of sorted(), min(), max() and list.sort()
kf: Callable[[int], int] = neg
ys = [3, 1, 2]
ys.sort(key=kf)
print(sorted([3, 1, 2], key=kf), min([3, 1, 2], key=kf), max(3, 1, 2, key=kf), ys)


# a conditional expression whose arms are functions, where a Callable is expected: each arm
# becomes the Callable in its own branch (#236)
def inc(x: int) -> int:
    return x + 1


class Shift:
    def __init__(self, k: int) -> None:
        self.k = k

    def by(self, x: int) -> int:
        return x + self.k


def arms(cond: bool, other: bool) -> None:
    k = 3
    f: Callable[[int], int] = inc if cond else double
    g: Callable[[int], int] = inc if cond else double if other else neg
    h: Callable[[int], int] | None = inc if cond else None
    fs: list[Callable[[int], int]] = [inc if cond else double, (lambda x: x * k) if cond else abs, Shift(5).by if cond else neg]
    d: dict[str, Callable[[int], int]] = {"f": double if cond else inc}
    print(f(10), g(100), h(1000) if h is not None else None, [x(-4) for x in fs], d["f"](5))
    print(maybe(inc if cond else None, 7), compose(inc if cond else double, neg)(4))


arms(True, False)
arms(False, True)
arms(False, False)
