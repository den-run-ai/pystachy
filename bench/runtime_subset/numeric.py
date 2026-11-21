"""math.hypot, math.dist and math.fma, pow(a, b, m), round(x, n) of an int and the int sum, moved
to runtime.py; the timed region excludes input construction."""
import math
import sys
from time import perf_counter


def hypot2(n: int, xs: list[float]) -> float:
    total = 0.0
    k = len(xs) - 1
    for i in range(n):
        total += math.hypot(xs[i % k], xs[i % k + 1])
    return total


def hypot3(n: int, xs: list[float]) -> float:
    total = 0.0
    k = len(xs) - 2
    for i in range(n):
        total += math.hypot(xs[i % k], xs[i % k + 1], xs[i % k + 2])
    return total


def dist(n: int, points: list[list[float]]) -> float:
    total = 0.0
    k = len(points) - 1
    for i in range(n):
        total += math.dist(points[i % k], points[i % k + 1])
    return total


def fma(n: int, xs: list[float]) -> float:
    total = 0.0
    k = len(xs) - 2
    for i in range(n):
        total += math.fma(xs[i % k], xs[i % k + 1], xs[i % k + 2])
    return total


def powmod(n: int, bases: list[int], exps: list[int], mods: list[int]) -> float:
    total = 0
    for i in range(n):
        total += pow(bases[i % len(bases)], exps[i % len(exps)], mods[i % len(mods)]) % 1000
    return float(total)


def round_int(n: int, xs: list[int]) -> float:
    total = 0
    for i in range(n):
        total += round(xs[i % len(xs)], -(i % 9) - 1) % 1000003
    return float(total)


def sum_int(n: int, xs: list[int]) -> float:
    total = 0
    for i in range(n):
        total += sum(xs, i % 7) % 1000
    return float(total)


kind = sys.argv[1]
n = int(sys.argv[2])
floats = [((i * 2654435761) % 1000003 - 500000) / 977.0 for i in range(1024)]
points3 = [[floats[(i + j) % 1024] for j in range(3)] for i in range(64)]
points64 = [[floats[(i * 7 + j) % 1024] for j in range(64)] for i in range(16)]
ints = [(i * 2654435761) % 1000003 - 500000 for i in range(4096)]
bases = [(i * 6364136223846793 + 1442695040888963407 % 1000003) % 9223372036854775783 for i in range(1, 64)]
exps = [65537, 9223372036854775782, 3, 1000000006, 4611686018427387847, -1, -65537]
mods61 = [9223372036854775783, 2305843009213693951, -9223372036854775783, 9223372036854775807 - 24]
mods31 = [1000000007, 998244353, 2147483647, -1000000007]

begin = perf_counter()
value = 0.0
if kind == "hypot":
    value = hypot2(n, floats)
elif kind == "hypot-3":
    value = hypot3(n, floats)
elif kind == "dist-3":
    value = dist(n, points3)
elif kind == "dist-64":
    value = dist(n, points64)
elif kind == "fma":
    value = fma(n, floats)
elif kind == "powmod":
    value = powmod(n, bases, exps, mods61)
elif kind == "powmod-31":
    value = powmod(n, bases, exps, mods31)
elif kind == "round-int":
    value = round_int(n, ints)
elif kind == "ints-sum":
    value = sum_int(n, ints)
else:
    raise ValueError("unknown workload")
elapsed = perf_counter() - begin
print(value.hex(), elapsed)
