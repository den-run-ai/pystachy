# math.dist is CPython's: the vector_norm of the differences, math.hypot's (lossless scaling,
# exact squares, the root corrected), so its last bit agrees at any magnitude and in any number
# of dimensions; an infinite difference gives inf, else a nan gives nan. The points are lists or
# tuples of numbers (also NamedTuples and objects with __iter__), each made a float.
import math
from math import dist
from typing import Iterator, NamedTuple


class P(NamedTuple):
    x: float
    y: float


class Q(NamedTuple):
    n: int
    x: float


class Path:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[float]:
        return iter(self.xs)


class Loud:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[float]:
        print("iter", self.xs)
        return iter(self.xs)


def maybe(n: int) -> tuple[float, float] | None:
    return (float(n), 1.0) if n > 0 else None


e: list[float] = []
print(dist((1.0, 2.0, 3.0), (4.0, 2.0, -1.0)), dist((1, 2, 3), (4, 2, -1)), dist([1.0], [3.0]), dist((14, 1), (2, -4)))
print(dist((True, True, False, False, True, True), (True, False, True, False, False, False)), dist(e, e), dist([1, 2], [3.5, 4.5]))
print(dist((13.25, 12.5, -3.25), (13.25, 12.5, -3.25)), dist((-0.0,), (0.0,)), dist((0.0,), (-0.0,)), dist((-5,), (3,)))
print(dist((1.5, 1.5, 0.5), (0, 0, 0)), dist((1.5, 0.5, 1.5), (0, 0, 0)), dist(P(3.0, 4.0), P(0.0, 0.0)), dist(Path([1.0, 1.0]), [0.0, 0.0]))
print(dist([2**53 + 1, 0], [0, 0]), dist({3: "a", 4: "b"}, (0, 0)), dist([0.1] * 100, [0.0] * 100), dist([1e-300] * 20, [-1e-300] * 20))
print(dist((), ()), dist((1, 2.5), (0.0, 0)), dist(Q(3, 4.0), (0, 0.0)), dist((True, 2**53 + 1, 0.25), (False, 2**53, 0)), dist(Loud([3.0]), Loud([1.0])))
try:
    print(dist((1, 2, 3, 4), (5, 6, 7)))
except ValueError as err:
    print("ValueError:", err)
try:
    print(dist([1.0] * 17, [1.0] * 18))
except ValueError as err:
    print("ValueError:", err)
try:
    print(dist(maybe(3), (0.0, 0.0)))
    print(dist((0.0, 0.0), maybe(0)))
except TypeError as err:
    print("TypeError:", err)
try:
    print(dist(Loud([1.0, 2.0]), maybe(0)))  # (tuple(p) first: its __iter__ runs)
except TypeError as err:
    print("TypeError:", err)

# infs and nans: any infinite difference is inf, whatever nan there is
values = [-math.inf, -10.5, -0.0, 0.0, 10.5, math.inf, math.nan]
counts = [0, 0, 0]
for a in values:
    for b in values:
        for c in values:
            for d in values:
                r = dist([a, b], [c, d])
                counts[0 if math.isinf(r) else 1 if math.isnan(r) else 2] += 1
print(counts)

# the extremes: no overflow or underflow on the way
fourthmax = 1.7976931348623157e308 / 4.0
print([dist([fourthmax] * n, [0.0] * n) for n in range(0, 32, 3)])
print([dist([-fourthmax] * n, [fourthmax] * n) for n in (1, 2, 3)])
for k in range(0, 32, 4):
    scale = 2.2250738585072014e-308 / 2.0**k
    print(k, dist((4 * scale, 3 * scale), (0.0, 0.0)) == 5 * scale, dist((0.0, 0.0), (4 * scale, 3 * scale)).hex())
seed = 5


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


def coord() -> float:
    k = rnd() % 6
    if k == 0:
        return (rnd() / 2147483648.0 - 0.5) * 2.0 ** (rnd() % 2098 - 1074)
    if k == 1:
        return [0.0, -0.0, 5e-324, 1.7976931348623157e308, -1.7976931348623157e308, 1e154, 1e-160][rnd() % 7]
    return (rnd() / 2147483648.0 - 0.5) * 2.0 ** (rnd() % 40 - 20)


h = 0
for i in range(4000):
    n = rnd() % 20
    p = [coord() for _ in range(n)]
    q = [coord() for _ in range(n)]
    if rnd() % 3 == 0:
        q = [x * (1.0 + (rnd() % 5 - 2) * 2.0**-52) for x in p]  # nearly the same point
    s = dist(p, q).hex()
    for ch in s:
        h = (h * 131 + ord(ch)) % 1000000007
print(h)
