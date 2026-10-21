# pystachy: dynamic-any
# x = y = v of a computed number: one object, which both names hold where they become Any
# values, as CPython assigns it to both (#807)
from typing import Any

x = y = int("1000")
a: Any = x
b: Any = y
print(a is b, id(a) == id(b))
f = g = float("2.5")
c: Any = f
d: Any = g
print(c is d, id(c) == id(d))


def local() -> None:
    p = q = int("2000") + 1
    m: Any = p
    n: Any = q
    print(m is n, id(m) == id(n), m == 2001)


local()
