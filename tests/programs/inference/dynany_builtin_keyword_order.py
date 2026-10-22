# pystachy: dynamic-any
# a builtin method called through an Any value with a keyword argument it does not take: the
# arguments are evaluated first, then TypeError, as CPython binds them (#826)
from typing import Any


def side(s: str) -> int:
    print("evaluated", s)
    return 1


x: Any = []
try:
    x.append(object=side("append"))
except TypeError:
    print("TypeError")
try:
    x.append(object=1)
except TypeError:
    print("TypeError")
d: Any = {}
try:
    d.get(key=side("get"))
except TypeError:
    print("TypeError")
print(x, d)
# with a keyword argument it takes and positional arguments it does not: found, then the
# arguments evaluated, then CPython's TypeError (#826)
xs: Any = [3, 1, 2]
try:
    xs.sort(side("sort positional"), key=side("sort key"))
except TypeError as e:
    print("TypeError", e)
try:
    d.update({}, {}, a=side("update"))
except TypeError as e:
    print("TypeError", e)
print(xs, d)
