# pystachy: dynamic-any
# is and id() of numbers and strs held as Any values (compare with CPython)
from typing import Any

a: Any = 1000
b: Any = int("1000")
print(a is b, id(a) == id(b))
c: Any = 1.5
d: Any = c
print(c is d, id(c) == id(d))
e: Any = float("1.5")
print(c is e, id(c) == id(e))
s: Any = "x" * 3
t: Any = "".join(["x", "x", "x"])
print(s == t, s is t, id(s) == id(t))
