# lib/statistics.py: CPython 3.13's statistics with its marked edits (lib/README.md), against
# CPython's own: fmean() with and without weights, median(), median_low(), median_high(),
# median_grouped(), quantiles(), geometric_mean(), mode(), multimode() and StatisticsError (cases
# after CPython's Lib/test/test_statistics.py and the docstrings), on lists, tuples, sets, dicts,
# strs and objects with __iter__; fmean()'s weights through _sumprod(), the port of math.sumprod(),
# on inputs from a linear congruential generator with infinities, NaNs, overflows and cancellations
import math
import statistics
from statistics import (StatisticsError, fmean, geometric_mean, median, median_grouped, median_high,
                        median_low, mode, multimode, quantiles)
from typing import Iterator

inf = math.inf
nan = math.nan


class Bag:
    # an iterable with __iter__ alone (CPython's iterators without __len__)
    def __init__(self, items: list[float]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[float]:
        return iter(self.items)


class Sized:
    # an iterable with __iter__ and __len__, which list() and sorted() call as a length hint
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[int]:
        print("  Sized.__iter__")
        return iter(self.items)

    def __len__(self) -> int:
        print("  Sized.__len__")
        return len(self.items)


class Unsized:
    # an iterable whose __len__ raises TypeError, as one whose length is unknown may: CPython's
    # fmean() catches it and counts the items, and math.sumprod() iterates without len()
    def __init__(self, items: list[float]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[float]:
        return iter(self.items)

    def __len__(self) -> int:
        raise TypeError("length unknown")


# StatisticsError is a ValueError
try:
    raise StatisticsError("boom")
except ValueError as e:
    print(type(e).__name__, e, isinstance(e, StatisticsError), repr(e))

# fmean() without weights
print(fmean([3.5, 4.0, 5.25]), fmean([1, 2, 3, 4, 4]), fmean([True, False, True, True, False]))
print(fmean((3.5, 4.0, 5.25)), fmean(Bag([3.5, 4.0, 5.25])), fmean([-1.5]), fmean({1: "a", 2: "b"}))
print(fmean([1e100, 1.0, -1e100]), fmean([0.1] * 10), fmean([2**53 + 1, 2**53 + 3]), fmean([-0.0]))
print(fmean([10.0, nan]), fmean([nan, inf]), fmean([10.0, inf]), fmean([-inf, 1.0]))
print(fmean(Sized([1, 2, 3, 5])))
print(fmean(Unsized([3.5, 4.0, 5.25])), fmean(Unsized([10.0, 20.0, 30.0]), [1, 2, 3]))
try:
    print(fmean(Unsized([1.0, 2.0]), [1, 2, 3]))
except StatisticsError as e:
    print(type(e).__name__, e)
for bad in [[inf, -inf], [1e308, 1e308]]:
    try:
        print(fmean(bad))
    except (ValueError, OverflowError) as e:
        print(type(e).__name__, e)
nothing: list[float] = []
try:
    print(fmean(nothing))
except StatisticsError as e:
    print("StatisticsError:", e)
try:
    print(fmean(Bag(nothing)))
except StatisticsError as e:
    print("StatisticsError:", e)

# fmean() with weights (test_weights, and _sumprod()'s int, bool and float paths)
print(fmean([10, 10, 10, 50], [0.25] * 4), fmean([10, 10, 10, 50]))
print(fmean([10, 10, 20], [0.25, 0.25, 0.50]), fmean([10, 10, 20, 20]))
print(fmean(Bag([10.0, 10.0, 20.0]), Bag([0.25, 0.25, 0.50])), fmean([1, 2, 4], weights=[1, 2, 3]))
print(fmean([1.5, 2.25, 4.0], [1, 2, 3]), fmean([1, 2, 3], [0.5, 0.25, 0.25]), fmean((1.5, 2.5), (3, 1)))
print(fmean([1.5, 2.25, 4.0], [True, False, True]), fmean([True, True, False], [2.5, 1.5, 4.0]))
print(fmean([3, 5, 7], [True, False, True]), fmean([True, False], [True, True]), fmean([2, 4], (1, 3)))
print(fmean([1e100, 1.0, -1e100], [1.0, 1.0, 1.0]), fmean([0.1, 0.2, 0.3], [3.0, 2.0, 1.0]))
print(fmean([1e200, 1e200], [1e200, 1.0]), fmean([1e300, -1e300, 1.0], [1e10, 1e10, 1.0]))
print(fmean([1.0, inf, 2.0], [1.0, 1.0, 1.0]), fmean([1.0, nan], [1.0, 1.0]), fmean([inf, 1.0], [0.0, 1.0]))
print(fmean([5e-324, 5e-324], [0.5, 0.5]), fmean([1.7976931348623157e308, 1.0], [2.0, 1.0]))
print(fmean([2.0, 3.0], [-1.0, 3.0]), fmean([1.0, 2.0, 3.0], {0: "", 1: "", 2: ""}))
for d, w in [([10.0, 20.0, 30.0], [1.0, 2.0]), ([10.0, 20.0], [-1.0, 1.0]), (nothing, nothing),
             ([10.0, 20.0], [0.0, 0.0]), ([1.0], [inf])]:
    try:
        print(fmean(d, w))
    except StatisticsError as e:
        print("StatisticsError:", e)
try:
    print(fmean(Bag([10.0, 20.0, 30.0]), [1, 2]))
except StatisticsError as e:
    print("StatisticsError:", e)

# fmean() with weights on generated inputs: the float path, its extended precision and its end
# where a product or a sum is not finite (C's math.sumprod() in CPython, _sumprod() here)
seed = 20261013


def rand(n: int) -> int:
    # an int in [0, n), from a 31-bit linear congruential generator (glibc's constants)
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed >> 4) % n


SPECIAL = [0.0, -0.0, inf, -inf, nan, 5e-324, 2.2250738585072014e-308, 1.7976931348623157e308,
           -1.7976931348623157e308, 1e300, 1e-300, 0.1, 3.0, -1.0]


def value() -> float:
    k = rand(20)
    if k == 0:
        return SPECIAL[rand(len(SPECIAL))]
    if k < 5:
        return (rand(2000001) - 1000000) * 10.0 ** (rand(80) - 40)
    if k < 8:
        return [1e16, -1e16, 1.0, -1.0, 1e-16][rand(5)]
    return (rand(2000001) - 1000000) / 1024.0


line: list[str] = []
for case in range(240):
    n = 1 + rand(12)
    xs = [value() for _ in range(n)]
    ws = [value() for _ in range(n)]
    if case % 3 == 0:
        ws = [abs(w) for w in ws]
    try:
        line.append(repr(fmean(xs, ws)))
    except StatisticsError as e:
        line.append("E:" + str(e)[:3])
    except (ValueError, OverflowError) as e:  # fsum(weights)'s
        line.append(type(e).__name__)
    if len(line) == 6:
        print(" ".join(line))
        line = []
ints = [rand(1000) - 500 for _ in range(400)]
wints = [rand(100) for _ in range(400)]
flags = [rand(2) == 1 for _ in range(400)]
floats = [(rand(2000001) - 1000000) / 1024.0 for _ in range(400)]
print(fmean(ints, wints), fmean(ints, flags), fmean(wints, floats), fmean(floats, flags))

# median(), median_low() and median_high()
print(median([1.0, 3.0, 5.0]), median([1.0, 3.0, 5.0, 7.0]), median([1.5, 2.5, 3.5, 4.5, 5.5, 6.5]))
print(median_low([1, 3, 5]), median_low([1, 3, 5, 7]), median_high([1, 3, 5]), median_high([1, 3, 5, 7]))
print(median_low([1, 2, 3, 4, 5, 6]), median_high([1, 2, 3, 4, 5, 6]), median([2.5, 3.1, 4.2, 5.7, 5.8]))
print(median((5.0, 1.0, 3.0, 2.0)), median_low({5, 1, 3, 2}), median_high("bca"), median_low(["b", "a"]))
print(median_low({3: "c", 1: "a", 2: "b"}), median_high({"b": 1, "a": 2}), median(Bag([2.0, 1.0])))
print(median_low([0.0, -0.0]), median_high([0.0, -0.0]), median([-0.0, 0.0]), median([inf, 1.0, -inf]))
print(median_low([3.0, nan, 1.0, 2.0]), median_high([nan, 3.0, 1.0, 2.0, 0.5]), median([nan, 2.0, 1.0]))
print(median_low([True, False, True]), median_high([(2, "b"), (1, "z"), (2, "a")]), median([42.5]))
print(median_low([2**62, -2**62, 7]), median_high([1.3e15]), median([1e308, 1e308]))
print(median_low(Sized([3, 1, 2])))
try:
    print(median(nothing))
except StatisticsError as e:
    print("median StatisticsError:", e)
try:
    print(median_low(()))
except StatisticsError as e:
    print("median_low StatisticsError:", e)
try:
    print(median_high(Bag(nothing)))
except StatisticsError as e:
    print("median_high StatisticsError:", e)
try:
    print(median_grouped(nothing, 2))
except StatisticsError as e:
    print("median_grouped StatisticsError:", e)

# median_grouped()
print(median_grouped([2, 2, 3, 3, 3, 4]), median_grouped([1, 2, 2, 3, 4, 4, 4, 4, 4, 5]))
print(median_grouped([12, 13, 14, 14, 14, 15, 15]), median_grouped([12, 13, 14, 14, 14, 14, 15]))
print(median_grouped([5, 10, 10, 15, 20, 20, 20, 20, 25, 25, 30], 5), median_grouped([16, 18, 18, 18, 18, 20, 20, 20, 22, 22, 22, 24, 24, 26, 28], 2))
print(median_grouped([5, 10, 10, 15, 20, 20, 20, 25, 25, 30], 5), median_grouped([2, 3, 4, 4, 4, 5]))
print(median_grouped([2, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6]), median_grouped([3, 4, 4, 4, 5, 5, 5, 5, 6, 6]))
print(median_grouped([2.25, 2.5, 2.5, 2.75, 2.75, 3.0, 3.0, 3.25, 3.5, 3.75], 0.25))
print(median_grouped([2.25, 2.5, 2.5, 2.75, 2.75, 2.75, 3.0, 3.0, 3.25, 3.5, 3.75], 0.25))
print(median_grouped([220, 220, 240, 260, 260, 260, 260, 280, 280, 300, 320, 340], 20))
print(median_grouped([5.3] * 5), median_grouped([68] * 2), median_grouped([4.3e17] * 10), median_grouped([23]))
demographics = [25] * 172 + [35] * 484 + [45] * 387 + [55] * 22 + [65] * 6
print(median_low(demographics), median_grouped(demographics, interval=10), round(median_grouped(demographics, interval=10), 1))
print(median_grouped((1.0, 2.0)), median_grouped({1, 2, 3}), median_grouped(["1", "2", "3"]), median_grouped([1, 2, 3], interval="2"))
print(median_grouped([1, 3, 3, 5], interval=True), median_grouped([True, True, False]))
for strs in [["", "", ""], ["a", "b", "c"]]:
    try:
        print(median_grouped(strs))
    except TypeError as e:
        print("TypeError:", e)
try:
    print(median_grouped([1, 2, 3], ""))
except TypeError as e:
    print("TypeError:", e)

# quantiles()
data = [120.0, 200.0, 250.0, 320.0, 350.0]
for n in [1, 2, 3, 4, 5, 6, 8, 10, 12, 15]:
    print(n, quantiles(data, n=n))
data = [100.0, 200.0, 400.0, 800.0]
for n in [1, 2, 3, 4, 5, 6, 8, 10, 12, 15]:
    print(n, quantiles(data, n=n, method="inclusive"))
print(quantiles([0.0, 100.0], n=10, method="inclusive"), quantiles([10.0], n=4), quantiles([10.0], n=4, method="inclusive"))
print(quantiles([10.0] * 5), quantiles([10.0] * 5, method="inclusive"), quantiles((3.0, 1.0, 2.0)), quantiles(Bag([1.0, 2.0])))
print(quantiles([1.5, -2.25, 1e10, 0.1, 7.0], n=7), quantiles([-0.0, 0.0, 1.0], n=3, method="inclusive"))
for n, method in [(0, "exclusive"), (-1, "exclusive"), (4, "X")]:
    try:
        print(quantiles([10.0, 20.0, 30.0], n=n, method=method))
    except StatisticsError as e:
        print("StatisticsError:", e)
    except ValueError as e:
        print("ValueError:", e)
try:
    print(quantiles(nothing, n=4))
except StatisticsError as e:
    print("StatisticsError:", e)

# medians and quantiles of generated data of every length from 1 to 40, with ties
for size in range(1, 41):
    xs = [float(rand(25)) / 4.0 for _ in range(size)]
    ks = [rand(10) for _ in range(size)]
    print(size, median(xs), median_low(ks), median_high(ks), median_grouped(ks), median_grouped(xs, 0.25),
          quantiles(xs, n=5), quantiles(xs, n=3, method="inclusive"))

# geometric_mean()
print(geometric_mean([54, 24, 36]), round(geometric_mean([54, 24, 36]), 9), geometric_mean([4.0, 9.0]), geometric_mean([17.625]))
print(geometric_mean([3.5, 4.0, 5.25]), geometric_mean((3.5, 4.0, 5.25)), geometric_mean(Bag([3.5, 4.0, 5.25])))
print(geometric_mean([2, 3, 5, 7]), geometric_mean([2.0, 3.0, 5.0, 7.0]), geometric_mean([12, 17, 13, 5, 120, 7]))
print(geometric_mean([54.0 * 2.0 ** 1000, 24.0 * 2.0 ** 1000, 36.0 * 2.0 ** 1000]), geometric_mean([54.0 * 2.0 ** -1000, 24.0 * 2.0 ** -1000]))
print(geometric_mean([10.0, nan]), geometric_mean([nan, inf]), geometric_mean([10.0, inf]), geometric_mean([3.0, 0.0, 5.0]))
print(geometric_mean([3.0, -0.0, 5.0]), geometric_mean([0.0, nan]), geometric_mean([0.0, inf]), geometric_mean([0.0, 0.0]))
print(geometric_mean([x for x in range(1, 100)]), geometric_mean([x for x in range(500, 10000, 3)]))
for d in [[3.5, -4.0, 5.25], [0.0, -4.0, 5.25], [3.5, -inf, 5.25], nothing]:
    try:
        print(geometric_mean(d))
    except StatisticsError as e:
        print("StatisticsError:", e)
try:
    print(geometric_mean([inf, -inf]))
except StatisticsError as e:
    print("StatisticsError:", e)

# mode() and multimode()
print(mode([1, 1, 2, 3, 3, 3, 3, 4]), mode(["red", "blue", "blue", "red", "green", "red", "red"]))
print(mode(["red", "red", "green", "blue", "blue"]), mode("abcbdb"), mode("fe fi fo fum fi fi".split()))
print(mode([1, 1, 2, 2, 2, 2, 3, 4, 5, 6, 6, 6, 6, 7, 8, 9, 9]), mode([x for x in range(10)]), mode([1, 1, 1, 1, 3, 4, 7, 9, 0, 8, 2]))
print(mode({"a": 1, "b": 2}), mode((3, 3, 1)), mode([(1, "a"), (2, "b"), (1, "a")]), mode([2**62, -5, 2**62]))
print(multimode("aabbbbbbbbcc"), multimode("aabbbbccddddeeffffgg"), multimode(""), multimode([3, 1, 3, 1, 2]))
print(multimode([(1, "x"), (1, "x"), (0, "y")]), multimode({7, 3}), multimode(["b", "a", "b", "a"]))
for i in range(10):
    discrete = [x for x in range(10)] + [i]
    print(mode(discrete), end=" ")
print()
empty: list[str] = []
print(multimode(empty))
try:
    print(mode(empty))
except StatisticsError as e:
    print("StatisticsError:", e)

# an uncaught StatisticsError ends the program as CPython's does
print(statistics.median_high(empty))
