# math.isclose(a, b, *, rel_tol=1e-09, abs_tol=0.0), CPython's math_isclose_impl: equal values
# (two infinities of one sign) are close, an infinity is close to nothing else, NaN to nothing,
# and otherwise |b - a| <= max(rel_tol * |a|, rel_tol * |b|, abs_tol). Ints and bools are taken
# as floats; a negative tolerance raises ValueError('tolerances must be non-negative').
import math
from math import isclose

inf = math.inf
nan = math.nan
cases = [(1.0, 1.0), (1.0, 1.0 + 1e-9), (1.0, 1.0 + 2e-9), (1e8, 1e8 + 1.0), (1e8, 1e8 + 0.1),
         (0.0, 1e-10), (0.0, 0.0), (-0.0, 0.0), (inf, inf), (-inf, -inf), (inf, -inf), (inf, 1e308),
         (nan, nan), (nan, 1.0), (1e-300, 2e-300), (-1.0, 1.0), (5e-324, 0.0), (1.7976931348623157e308, inf)]
for a, b in cases:
    print(a, b, isclose(a, b), math.isclose(b, a), isclose(a, b, rel_tol=0.5), isclose(a, b, abs_tol=1e-9),
          isclose(a, b, rel_tol=0.0, abs_tol=0.0), isclose(a, b, rel_tol=inf), isclose(a, b, abs_tol=inf))
print(isclose(1, 1), isclose(True, 1.0), isclose(3, 3.0000000001), isclose(10, 11, rel_tol=0.1), isclose(10, 11, abs_tol=1))
print(isclose(b=1.0, a=1.0 + 1e-12), isclose(1.0, b=1.0), isclose(9007199254740993, 9007199254740992.0, rel_tol=0))
print(isclose(1.0, 1.1, abs_tol=0.1), isclose(1.0, 1.1, abs_tol=0.10000000000000009), isclose(1.0, 1.1, rel_tol=nan))
for rel, ab in [(-1e-9, 0.0), (0.0, -1.0), (-inf, inf), (0.0, -0.0)]:
    try:
        print(isclose(1.0, 1.0, rel_tol=rel, abs_tol=ab))
    except ValueError as e:
        print("ValueError", e)
f = math.isclose
print(f(2.0, 2.0 + 4e-9), f(2.0, 2.0 + 4e-9, rel_tol=1e-8))
x: float | None = None
try:
    print(isclose(1.0, x))
except TypeError as e:
    print("TypeError", e)
y: float | None = 1.0
print(isclose(1.0, y))


# arguments: evaluated in the order written; a None among them raises once all are evaluated
def num(tag: str, v: float) -> float:
    print("eval", tag, end="; ")
    return v


print(isclose(num("a", 1.0), num("b", 1.05), abs_tol=num("abs", 0.1), rel_tol=num("rel", 0.0)))
print(isclose(b=num("b", 2.0), a=num("a", 2.0)))
try:
    print(isclose(num("a", 1.0), num("b", 1.0), rel_tol=num("rel", -1.0)))
except ValueError as e:
    print("ValueError", e)
