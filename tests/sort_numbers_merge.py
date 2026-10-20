# Sorting lists of ints and floats long enough that timsort merges its runs (64 items or more):
# pseudo-random items, runs that one side wins many times in a row (where the merges gallop),
# descending runs, few distinct values, the 64-bit and float extremes, sort(reverse=True) and
# sorted(); zeros of either sign, which compare equal and so keep their order (the sort is
# stable, also in reverse); and NaNs, which compare false both ways, so that where they end up
# shows each step CPython's timsort takes (insertion below minrun, runs, merges and gallops).
import math


def lcg(seed: int, n: int, mod: int) -> list[int]:
    out: list[int] = []
    x = seed
    for _ in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out.append(x % mod)
    return out


def show(name: str, xs: list[int]) -> None:
    ys = sorted(xs)
    zs = xs.copy()
    zs.sort(reverse=True)
    ordered = all(ys[i] <= ys[i + 1] for i in range(len(ys) - 1))
    check = sum((i + 1) * (v % 1000003) for i, v in enumerate(ys)) % 1000003
    print(name, len(ys), ordered, ys[:4], ys[-3:], check, zs[:3], zs == ys[::-1])


def fshow(name: str, xs: list[float]) -> None:
    ys = sorted(xs)
    zs = sorted(xs, reverse=True)
    ordered = all(ys[i] <= ys[i + 1] for i in range(len(ys) - 1))
    signs = "".join(["+" if math.copysign(1.0, v) > 0 else "-" for v in ys if v == 0.0])
    rsigns = "".join(["+" if math.copysign(1.0, v) > 0 else "-" for v in zs if v == 0.0])
    print(name, len(ys), ordered, ys[:3], ys[-2:], sum(ys[::7]), signs, rsigns)


show("random", lcg(7, 1000, 1000000))
show("few values", lcg(11, 700, 5))
show("two runs", list(range(0, 2000, 2)) + list(range(1, 300, 2)))
show("blocks", list(range(500, 600)) + list(range(0, 100)) + list(range(250, 350)) + list(range(100, 200)))
show("descending runs", list(range(300, 200, -1)) + list(range(100, 0, -1)) + list(range(200, 100, -1)))
show("extremes", [9223372036854775807, -9223372036854775808, 0, -1, 1] * 30 + lcg(3, 100, 1000))
fs = [float(v) / 7.0 - 50.0 for v in lcg(5, 600, 1000)]
fshow("floats", fs)
zeros: list[float] = []
for i in range(130):
    zeros.append(0.0 if i % 3 else -0.0)
    zeros.append(float(i % 5) - 2.0)
fshow("zeros", zeros)
fshow("infinities", [math.inf, -math.inf, 1e308, -1e308, 5e-324, -5e-324] * 20 + fs[:50])


def nans(n: int, every: int) -> None:
    xs = [float(v) / 7.0 for v in lcg(n + every, n, 1000)]
    for i in range(0, n, every):
        xs[i] = math.nan
    ys = sorted(xs)
    zs = xs.copy()
    zs.sort(reverse=True)
    pos = [i for i, v in enumerate(ys) if math.isnan(v)]
    rpos = [i for i, v in enumerate(zs) if math.isnan(v)]
    check = 0
    for i, v in enumerate(ys):
        if not math.isnan(v):
            check = (check * 31 + int(v * 7) + i) % 1000003
    print("nans", n, every, pos[:10], rpos[:10], len(pos), check)


def nan_runs(name: str, parts: list[list[int]], every: int) -> None:
    # ascending runs (a NaN ends none) whose merges gallop: there the comparisons are a search's
    xs: list[float] = []
    for p in parts:
        for v in p:
            xs.append(float(v))
    for i in range(every // 2, len(xs), every):
        xs[i] = math.nan
    ys = sorted(xs)
    zs = sorted(xs, reverse=True)
    pos = [i for i, v in enumerate(ys) if math.isnan(v)]
    rpos = [i for i, v in enumerate(zs) if math.isnan(v)]
    check = 0
    for i, v in enumerate(ys):
        if not math.isnan(v):
            check = (check * 31 + int(v) + i) % 1000003
    print("nan runs", name, every, pos[:8], rpos[:8], len(pos), check)


for n, every in [(20, 3), (63, 17), (65, 3), (200, 17), (1000, 3), (1000, 101)]:
    nans(n, every)
for every in [7, 23, 37]:
    nan_runs("two", [list(range(0, 2000, 2)), list(range(1, 300, 2))], every)
    nan_runs("blocks", [list(range(500, 600)), list(range(0, 100)), list(range(250, 350)), list(range(100, 200))], every)
