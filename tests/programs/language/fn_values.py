# Functions as values: a def or a builtin passed, stored, returned and called through. Each value is
# typed by the function it is, so a call through it compiles as a call of that function (a
# template's, for the call's argument types)
import math
import operator
from math import floor


def double(x):
    return x * 2


def shout(s: str, end: str = "!") -> str:
    return s.upper() + end


def apply(f, x):
    return f(x)


def twice(f, x):
    return f(f(x))


def compose_apply(f, g, x):
    return f(g(x))


def pick(name):
    if name == "len":
        return len
    return len


def table(f, xs):
    out = []
    for x in xs:
        out.append(f(x))
    return out


def fold(f, xs, acc):
    for x in xs:
        acc = f(acc, x)
    return acc


def with_default(x, f=double):
    return f(x)


def call_kw(f):
    return f("hey", end="?")


print(apply(double, 5), apply(double, "ab"), apply(double, 1.5))
print(twice(double, 3), twice(double, 4))
print(apply(len, "hello"), apply(abs, -7), apply(str, 42) + "!", apply(int, "12") + 1)
print(compose_apply(str, len, [1, 2, 3]), compose_apply(double, len, "four"))
print(table(double, [1, 2, 3]), table(repr, ["a", "b"]), table(math.sqrt, [4.0, 9.0]))
print(fold(operator.add, [1, 2, 3, 4], 0), fold(operator.mul, [1, 2, 3, 4], 1), fold(max, [3, 9, 2], 0))
print(fold(operator.add, ["x", "y"], ""), pick("len")("abcd"))
print(with_default(21), with_default(5, abs), with_default("z", repr))
print(call_kw(shout), shout("ok"))
f = double
g = f
print(f(10), g("-"), (f, 1)[0](7))
fs = [double, double]
print([h(2) for h in fs], len(fs))
show = print
show("via", "print", sep="-", end=".\n")
if f:
    print("a function is true")
print(isinstance(f, int), isinstance(len, object))


def name_of(f):
    return f.__name__


print(double.__name__, len.__qualname__, math.sqrt.__name__, name_of(shout), name_of(abs), name_of(operator.add))


class Scaler:
    def __init__(self, k: int) -> None:
        self.k = k
        self.f = double
        self.show = repr
        self.root = math.sqrt
        self.floor = floor

    def run(self, x: int) -> str:
        return self.show(self.f(x) * self.k)


sc = Scaler(3)
print(sc.run(5), sc.f(1), sc.show("s"), sc.root(16.0), sc.floor(2.5))
