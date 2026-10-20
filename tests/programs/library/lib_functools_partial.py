# functools.partial (lib/functools.py, adapted from CPython 3.13.16's pure-Python class):
# stored positional and keyword arguments, keywords given at the call replacing stored ones,
# partials of partials flattened into one, .func/.args/.keywords, CPython's TypeError for a
# first argument that is not callable, and the order arguments are evaluated in
import functools
from functools import partial


def add(a: int, b: int, c: int = 0) -> int:
    return a * 100 + b * 10 + c


def joiner(*parts: str, sep: str = "-") -> str:
    return sep.join(parts)


def note(s: str) -> str:
    print("eval", s)
    return s


class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def mul(self, x: int) -> int:
        return self.k * x

    def __call__(self, x: int, y: int = 1) -> int:
        return self.k * x + y


p = partial(add, 1)
print(p(2), p(2, 3), p(2, c=5), p(b=4))
q = partial(add, 1, c=7)
print(q(2), q(2, c=9), q.args, q.keywords, q.func is add)
r = partial(q, 3)
print(r(), r.args, r.keywords, r.func is add, isinstance(r.func, partial))
s = partial(partial(add, b=4), 2)
print(s(), s(c=1), s.args, s.keywords)
t = partial(partial(add, c=1), b=2, c=3)
print(t(5), t.keywords, len(t.keywords))
print(isinstance(p, functools.partial), callable(p), callable(add), callable(5))

# builtins, varargs, bound methods, callable objects, lambdas and closures
base2 = partial(int, base=2)
print(base2("101"), base2("11111111"))
j = partial(joiner, "x", sep="+")
print(j(), j("y", "z"), j("y", sep="/"), joiner("a", "b"))
sc = Scale(3)
print(partial(sc.mul)(4), partial(sc, 2)(), partial(sc, 2)(y=5), partial(sc, y=0)(7))
print(partial(lambda x, y: x + y, "é")("ß"))


def outer(n: int) -> int:
    def inner(a: int, b: int) -> int:
        return a * n + b

    return partial(inner, 5)(1)


print(outer(10))

# partials as keys, in containers, passed around
print(sorted([3, 1, 2], key=partial(add, 1)), max([3, 1, 2], key=partial(add, b=0)))
fs = [partial(add, 1), partial(add, 2)]
print([f(3) for f in fs], list(map(partial(add, 1), [1, 2])))


def apply(f, x: int) -> int:
    return f(x)


print(apply(partial(add, 9), 9), apply(p, 1))

class Pipeline:
    def __init__(self, k: int) -> None:
        self.step = partial(add, k)

    def run(self, xs: list[int]) -> list[int]:
        return [self.step(x) for x in xs]


print(Pipeline(4).run([1, 2]))

# arguments are evaluated where partial() is called, then again where it is called
e = partial(joiner, note("a"), sep=note("b"))
print(e(note("c"), note("d")))

# not callable: CPython's TypeError, raised by partial() itself
for bad in range(2):
    try:
        partial(bad)
    except TypeError as ex:
        print("TypeError:", ex)
try:
    partial("joiner")
except TypeError as ex:
    print("TypeError:", ex)
