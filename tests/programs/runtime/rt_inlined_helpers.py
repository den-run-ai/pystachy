# The runtime's small functions that the JIT tier inlines into a loop (#705): their results and
# errors in each iteration, as CPython's, with every value read at run time (rt_inlined_helpers.in)
# so that no optimizer folds them: list[float] reads and assignments (negative indices too), float
# division, math.sqrt(), int //, % and shifts, and float-to-int conversion.
import math
import sys


def reads(xs: list[float], idx: list[int]) -> float:
    s = 0.0
    for i in idx:
        s += xs[i]
    return s


def writes(xs: list[float], idx: list[int], v: float) -> list[float]:
    for i in idx:
        xs[i] = v
        v += 1.0
    return xs


def ratios(xs: list[float], ds: list[float]) -> float:
    s = 0.0
    for i in range(len(xs)):
        s += xs[i] / ds[i]
    return s


def roots(xs: list[float]) -> float:
    s = 0.0
    for x in xs:
        s += math.sqrt(x)
    return s


def ints(a: list[int], b: list[int]) -> list[int]:
    out: list[int] = []
    for i in range(len(a)):
        out.append(a[i] // b[i])
        out.append(a[i] % b[i])
        out.append((a[i] << (b[i] & 7)) >> (b[i] & 3))
    return out


def shifts(a: list[int], b: list[int]) -> int:
    s = 0
    for i in range(len(a)):
        s += a[i] >> b[i]
    return s


def truncs(xs: list[float]) -> int:
    s = 0
    for x in xs:
        s += int(x)
    return s


def at(i: int, log: list[str]) -> int:
    log.append(f"index {i}")
    return i


def order(xs: list[float], log: list[str]) -> float:
    # (each index is computed, with its effect, before the read that raises)
    s = 0.0
    for i in range(5):
        s += xs[at(i * 3, log)]
    return s


fs = [float(w) for w in sys.stdin.readline().split()]
ns = [int(w) for w in sys.stdin.readline().split()]
zs = [float(w) for w in sys.stdin.readline().split()]
print("reads", reads(fs, [0, 1, -1, -len(fs), 2]))
try:
    print(reads(fs, [0, len(fs)]))
except IndexError as error:
    print("reads past the end:", type(error).__name__, error)
try:
    print(reads(fs, [1, -len(fs) - 1]))
except IndexError as error:
    print("reads before the start:", type(error).__name__, error)
print("writes", writes(fs[:], [0, -1, 2], 0.5))
try:
    print(writes(fs[:], [1, len(fs)], 0.5))
except IndexError as error:
    print("writes past the end:", type(error).__name__, error)
print("ratios", ratios(fs, [w + 1.0 for w in fs]))
try:
    print(ratios(fs, zs))
except ZeroDivisionError as error:
    print("ratios by zero:", type(error).__name__, error)
print("roots", roots([abs(w) for w in fs]))
try:
    print(roots(fs))
except ValueError as error:
    print("roots of a negative:", type(error).__name__, error)
print("ints", ints(ns, [3, -3, 7, -7, 2, 5]))
try:
    print(ints(ns, [3, 0, 1, 1, 1, 1]))
except ZeroDivisionError as error:
    print("ints by zero:", type(error).__name__, error)
print("shifts", shifts(ns, [1, 2, 63, 64, 0, 3]))
try:
    print(shifts(ns, [1, -1, 0, 0, 0, 0]))
except ValueError as error:
    print("negative shifts:", type(error).__name__, error)
print("truncs", truncs(fs))
try:
    print(truncs(fs + [math.nan]))
except ValueError as error:
    print("truncs of nan:", type(error).__name__, error)
try:
    print(truncs(fs + [-math.inf]))
except OverflowError as error:
    print("truncs of inf:", type(error).__name__, error)
log: list[str] = []
try:
    print(order(fs, log))
except IndexError as error:
    print("order:", type(error).__name__, error)
print(log)
