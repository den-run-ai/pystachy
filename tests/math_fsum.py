# math.fsum is CPython's algorithm (Shewchuk's exact partials, rounded once, with its
# half-even correction): its last bit agrees, on sums that cancel, tie, overflow on the way or
# hold infs and nans, and on random ones. It takes what sum() takes; an int item is a float.
import math
from typing import Iterator, NamedTuple

M = 1.7976931348623157e308
H = 9.979201547673599e291  # half an ulp of M
cases: list[list[float]] = [
    [],
    [0.0],
    [-0.0, -0.0],
    [0.1] * 10,
    [1e100, 1.0, -1e100, 1e-100, 1e50, -1.0, -1e50],
    [1e16, 1.0, 1e-16],
    [1e-16, 1.0, 1e16],
    [2.0**53, 1.0, 2.0**-60],
    [2.0**53, 1.0, -2.0**-60],
    [2.0**53, -1.0, 2.0**-60],
    [2.0**53, 3.0, 2.0**-80, 2.0**-90],
    [-2.0**53, -1.0, -2.0**-60],
    [5e-324, 5e-324, -5e-324, 2.2250738585072014e-308],
    [M, -M, 1.0],
    [M, H, -H],
    [M, H * 0.999],
    [M, -H, -H],
    [1.0 / n for n in range(1, 2000)],
    [(-1.0) ** n / n for n in range(1, 2000)],
    [2.0**k * (1.0 if k % 3 else -1.0) for k in range(-1074, 1024, 7)],
    [1.3 ** (i + 1) - 1.3**i for i in range(600)] + [-(1.3**600)],
    [math.inf, 1.0],
    [1.0, -math.inf, -math.inf],
    [math.nan, 1.0],
    [math.inf, math.nan],
    [M, M],
    [-math.inf, M, M],
    [M, H],
    [math.inf, -math.inf],
    [math.nan, math.inf, -math.inf],
]
for xs in cases:
    try:
        r = math.fsum(xs)
        print(len(xs), repr(r), r.hex())
    except OverflowError as e:
        print(len(xs), "OverflowError:", e)
    except ValueError as e:
        print(len(xs), "ValueError:", e)


class Pts:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[float]:
        return iter(self.xs)


class P(NamedTuple):
    x: float
    y: float
    z: float


class Q(NamedTuple):
    n: int
    x: float


def maybe(n: int) -> list[float] | None:
    return [0.5] * n if n > 0 else None


ys: list[int] = [1, 2**53 + 1, -(2**53)]
print(math.fsum(ys), math.fsum([2**62, 2**62, -9223372036854775807]), math.fsum(range(100000)), math.fsum([True, False, True]))
print(math.fsum(x * 0.1 for x in range(10)), math.fsum((0.1, 0.2, 0.3)), math.fsum(Pts([1e100, 1.0, -1e100])))
print(math.fsum(P(1e16, 1.0, 1e-16)), math.fsum({3: "a", 4: "b"}), math.fsum(reversed([0.5, 1e20, -1e20])))
print(math.fsum(()), math.fsum((1, 2.5, True)), math.fsum((2**53 + 1, -(2**53), 0.5)), math.fsum(Q(2**53 + 1, 1.0)))
try:
    print(math.fsum(maybe(3)))
    print(math.fsum(maybe(0)))
except TypeError as e:
    print("TypeError:", e)
seed = 7


def rnd() -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed


SPECIAL = [0.0, -0.0, 5e-324, -5e-324, 2.2250738585072014e-308, M, -M, H, 1.0, -1.0, 0.5, 1e16, math.inf, -math.inf, math.nan]


def item() -> float:
    k = rnd() % 10
    if k == 0:
        return SPECIAL[rnd() % (len(SPECIAL) if rnd() % 3 == 0 else len(SPECIAL) - 3)]
    if k == 1:
        return float(rnd() % 2001 - 1000)
    if k == 2:
        return (rnd() / 2147483648.0 - 0.5) * 2.0 ** (rnd() % 2098 - 1074)
    if k == 3:
        return (rnd() / 1073741824.0 - 1.0) * M
    m = rnd() / 2147483648.0 + rnd() / 2147483648.0 / 2147483648.0
    return (m - 0.5) * 2.0 ** (rnd() % 120 - 60)


h = 0
counts = [0, 0, 0, 0]
for i in range(4000):
    xs = [item() for _ in range(rnd() % 14)]
    if rnd() % 3 == 0:
        # cancellation: the negations of the items, some of them halved or one ulp off, shuffled
        for j in range(len(xs)):
            xs.append(-xs[j] * [1.0, 1.0, 0.5, 1.0000000000000002][rnd() % 4])
        for j in range(len(xs) - 1, 0, -1):
            k = rnd() % (j + 1)
            t = xs[j]
            xs[j] = xs[k]
            xs[k] = t
    try:
        r = math.fsum(xs)
        s = r.hex()
        counts[0 if math.isfinite(r) else 1] += 1
    except OverflowError as e:
        s = str(e)
        counts[2] += 1
    except ValueError as e:
        s = str(e)
        counts[3] += 1
    for c in s:
        h = (h * 131 + ord(c)) % 1000000007
print(h, counts)
