# Comparisons of an int with a float decided at run time, exactly as CPython makes them: floats
# beyond the 64-bit range, negative floats whose truncation equals the int, and the neighbours of
# 2**63; (-1) ** n for an even and an odd n, and round() to far fewer digits than a float has.
import sys

n = len(sys.argv)                  # 3 (tests/run.sh passes a1 a2): values the compiler cannot fold
big = 9223372036854775807 - 3 + n  # 2**63 - 1
small = -big - 1                   # -2**63
neg = -n                           # -3
floats = [-1e19, -9.223372036854777856e18, -9.223372036854775808e18, -3.5, -2.5, -3.0, 9.223372036854775808e18, 1e19]
for f in floats:
    print(f, small < f, small == f, small > f, neg < f, neg == f, neg > f, big < f, big >= f)
print(float(small) == small, float(big) == big, float(big) > big)
for e in [n - 1, n, n + 1, 10 * n]:
    print(e, (-1) ** e, (-n) ** e)
huge = 1.4e308 / n * 3             # near the largest float
for d in [-401, -1000, -308, -309]:
    print(d, round(1.5e300 * n, d), round(huge, d), round(-huge, d), round(-2.5 * n, d), round(123.456, d))
