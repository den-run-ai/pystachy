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
