# pystachy: dynamic-any
# The bounds of a slice that are Any values, converted as CPython converts them once the slice is
# made: after every bound is evaluated and the receiver is tested, the step first (its 0's
# ValueError before a bound's TypeError); a dict's slice raises the KeyError of the slice (#782).
from typing import Any


def f(x: Any) -> Any:
    print("f", x)
    return x


d: Any = {"k": 1}
xs: Any = [1, 2, 3, 4]
w: Any = 5
nn: Any = None
bad: Any = "a"
zero: Any = 0
n: Any = 1
for lo, hi, st in [(1, 2, None), (None, "a", True), (None, None, None)]:
    try:
        print(d[lo:hi:st])
    except KeyError as err:
        print("dict:", err)
for o in [w, nn]:
    try:
        print(o[bad:])
    except TypeError as err:
        print("receiver:", err)
try:
    print(xs[bad::zero])
except (TypeError, ValueError) as err:
    print("step first:", type(err).__name__, err)
try:
    print(xs[1:2:bad])
except TypeError as err:
    print("step:", err)
try:
    print(xs[bad:f(2)])
except TypeError as err:
    print("later bound:", err)
print(xs[True:], xs[n:None:n + 1])
l = [1, 2, 3, 4]
ol: list[int] | None = None if n == 1 else l
try:
    print(l[bad::zero])
except (TypeError, ValueError) as err:
    print("typed step first:", type(err).__name__, err)
try:
    print(l[bad::0])
except (TypeError, ValueError) as err:
    print("typed step 0:", type(err).__name__, err)
try:
    print(l[bad:f(3)])
except TypeError as err:
    print("typed later bound:", err)
try:
    print(ol[bad:])
except TypeError as err:
    print("typed None:", err)
print(l[n::n + 1], "hello"[n:-n], (1, 2, 3)[n:])
l[n:3] = [7, 8, 9]
print(l)
del l[:n]
print(l)
try:
    l[bad:f(1)] = [0]
except TypeError as err:
    print("assign:", err)
try:
    del l[bad::zero]
except (TypeError, ValueError) as err:
    print("delete:", type(err).__name__, err)
print(l)
