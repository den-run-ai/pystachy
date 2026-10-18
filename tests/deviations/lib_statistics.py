# Documented deviations of lib/statistics (CPython 3.13's statistics with marked edits) from CPython.
import statistics
from statistics import fmean

# Pystachy's ints are 64-bit: fmean() with weights adds the products of ints as ints (as C's
# math.sumprod() does), and raises OverflowError where the sum leaves 64 bits: CPython prints
# 4.611686018427388e+18.
try:
    print(fmean([2**62, 2**62], [1, 1]))
except OverflowError as e:
    print("OverflowError:", e)

# The module's sumprod, math's where math has one (CPython), is _sumprod() where it has none, which
# returns float(math.sumprod(p, q)): CPython prints 11 0.
nothing: list[float] = []
print(statistics.sumprod([1, 2], [3, 4]), statistics.sumprod(nothing, nothing))
