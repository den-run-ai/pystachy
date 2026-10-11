# math.prod(iterable, *, start=1) multiplies left to right as CPython does: ints as ints, and
# floats as floats once a float is among the factors (the int start or items before it are
# converted then). It takes what sum() takes. (An empty list[float] and int overflow are in
# tests/deviations/math_prod.py.)
import math
from math import prod
from typing import Iterator


class Factors:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)


def item(x: int) -> int:
    print("item", x)
    return x


def first(x: int) -> int:
    print("start", x)
    return x


def maybe(n: int) -> list[int] | None:
    return [3] * n if n > 0 else None


e: list[int] = []
print(prod(e), prod(e, start=5), prod(e, start=2.5), prod(list(range(2, 8))), prod(range(1, 10), start=10))
print(prod([1, 2, 3, 4, 5]), prod([1.0, 2.0, 3.0, 4.0, 5.0]), prod([0, 1, 2]), prod([-3, 5, -7]), prod([3] * 39))
print(prod([2, 3], start=0.5), prod([0.5, 3.0], start=3), prod([True, False]), prod([True, True], start=7))
print(prod([3.0], start=2**53 + 1), prod([2**53 + 1, 3], start=1.0), prod([1.0], start=-(2**62) - 1))
print(prod([1e308, 10.0]), prod([-1e308, 10.0]), prod([0.0, math.inf]), prod([-0.0, 2.0]), prod([2.0, -0.0], start=-1))
print(prod([math.nan, 0.0]), prod([1e-320, 1e-10]), prod([5e-324, 0.5]), prod([5e-324, 0.75]), prod([math.inf, -1.0]))
print(prod((2, 3, 7)), prod((0.5, 0.25)), prod({2: "a", 5: "b"}), prod(Factors([4, 5, 6])), prod(reversed([2, 9])))
print(prod(x + 1 for x in range(6)), prod((x * 0.5 for x in range(1, 5)), start=3), prod(()), prod((), start=2.5))
print(prod((item(x) for x in range(1, 4)), start=first(10)))
print(prod([item(x) for x in range(1, 4)], start=first(10)))
try:
    print(prod(maybe(2), start=2))
    print(prod(maybe(0)))
except TypeError as err:
    print("TypeError:", err)
seed = 3


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


h = 0
for i in range(3000):
    xs = [(rnd() / 2147483648.0 - 0.5) * 2.0 ** (rnd() % 400 - 200) for _ in range(1 + rnd() % 9)]
    ns = [rnd() % 1001 - 500 for _ in range(rnd() % 7)]
    s = prod(xs).hex() + " " + prod(ns, start=1.5).hex() + " " + str(prod(ns)) + " " + str(prod(ns, start=rnd() % 3 - 1))
    for c in s:
        h = (h * 131 + ord(c)) % 1000000007
print(h)
