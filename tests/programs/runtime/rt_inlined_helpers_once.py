# The runtime's small functions that the JIT tier inlines where a loop calls them (#705), called
# also by functions that run once, whose calls of them stay calls of the runtime (marked noinline):
# their results and errors at both, as CPython's, with every value read at run time
# (rt_inlined_helpers_once.in) so that no optimizer folds them.
import math
import sys


def loop(xs: list[float], ns: list[int], ds: list[int]) -> float:
    s = 0.0
    for i in range(len(ds)):
        s += xs[i] / (xs[i + 1] + 10.0) + math.sqrt(abs(xs[i]))
        xs[i] = s
        k = ns[i] // ds[i] + ns[i] % ds[i] + (ns[i] >> (ds[i] & 7)) + (ns[i] << (ds[i] & 3))
        s += float(k) + float(int(xs[i + 1]))
    return s


def once(xs: list[float], k: int, d: float) -> float:
    print("read", xs[k], xs[-k - 1], int(xs[k]))
    xs[k] = d
    return math.sqrt(xs[k]) / d


def ints(a: int, b: int) -> int:
    print("ints", a // b, a % b)
    return (a >> b) + (a << 2)


fs = [float(w) for w in sys.stdin.readline().split()]
ns = [int(w) for w in sys.stdin.readline().split()]
ds = [int(w) for w in sys.stdin.readline().split()]
print("loop", loop(fs[:], ns, ds))
print("once", once(fs[:], 0, 4.0))
try:
    print(once(fs[:], len(fs), 1.0))
except IndexError as error:
    print("once past the end:", type(error).__name__, error)
try:
    print(once(fs[:], 4, 0.0))
except ZeroDivisionError as error:
    print("once by zero:", type(error).__name__, error)
try:
    print(once(fs[:], 5, -2.0))
except ValueError as error:
    print("once of a negative:", type(error).__name__, error)
print("ints", ints(ns[0], ns[1]))
try:
    print(ints(ns[2], ns[3]))
except ZeroDivisionError as error:
    print("ints by zero:", type(error).__name__, error)
try:
    print(ints(ns[4], ns[5]))
except ValueError as error:
    print("negative shift:", type(error).__name__, error)
print("loop again", loop(fs[:], ns, ds))
