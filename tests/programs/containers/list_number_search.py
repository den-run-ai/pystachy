# in, count(), index() and remove() of a list of ints, floats or bools (also | None) find the item
# equal to a number of another of those types, as CPython's == compares them
import math
import sys

big = 2**53 + 1
fs = [1.0, 2.0**53, -0.0, math.inf, 9.223372036854775808e18]
ints = [1, 2, -3, sys.maxsize, -sys.maxsize - 1]
bs = [True, False, True]
oi: list[int | None] = [1, None, 2]
of: list[float | None] = [None, 1.5, 3.0]
ob: list[bool | None] = [None, False]


def gi(f: bool) -> int | None:
    return 3 if f else None


def gf(f: bool) -> float | None:
    return 2.0 if f else None


print(1 in fs, 0 in fs, big in fs, 2**53 in fs, sys.maxsize in fs, True in fs, False in fs, fs.count(0), fs.index(1), fs.index(True))
print(1.0 in ints, 2.5 in ints, -3.0 in ints, math.nan in ints, math.inf in ints, 9.223372036854775807e18 in ints, -9.223372036854775808e18 in ints)
print(True in ints, ints.count(True), ints.count(1.0), ints.index(2.0), ints.index(True), ints.index(-3.0, 1, 3))
print(1 in bs, 0 in bs, 2 in bs, -1 in bs, 1.0 in bs, 0.5 in bs, bs.count(1), bs.count(1.0), bs.index(0), bs.index(0.0))
print(True in oi, 2.0 in oi, 2.5 in oi, oi.count(True), oi.index(2.0), 1 in of, 3 in of, of.count(3), of.index(3), 0 in ob, 0.0 in ob)
print(gi(True) in fs, gi(False) in fs, gf(True) in ints, gf(False) in ints, gi(True) not in fs)
xs = [1, 2, 3]
xs.remove(2.0)
ys = [1.0, 2.0]
ys.remove(True)
zs = [True, False]
zs.remove(0)
print(xs, ys, zs)
