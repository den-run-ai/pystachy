# pystachy: dynamic-any
# Union keys of classes hashed by identity (#1452) in a dynamic-Any program, whose dicts hash
# their keys as CPython does: a key of either class is stored and found once
from typing import Any


class A:
    pass


class B:
    pass


a = A()
b = B()
d: dict[A | B, str] = {a: "a"}
d[b] = "b"
d[a] = "a2"
s: set[A | B] = {a, b, a}
v: Any = 1
print(len(d), d[a], d[b], len(s), a in s, B() in s, v)
