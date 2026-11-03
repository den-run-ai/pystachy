# pystachy: dynamic-any
# copy.copy() and copy.deepcopy() of an object keep its int field's object, as CPython's give the
# copy the same int: read through Any, the original's and the copy's fields are one object, whether
# the original's field crossed into Any before the copy (its box exists) or after (made at the copy)
import copy
from typing import Any


class P:
    def __init__(self, n: int, f: float) -> None:
        self.n = n
        self.f = f


p = P(int("1000"), float("2.5"))
q = copy.copy(p)
r = copy.deepcopy(p)
a: Any = p.n
b: Any = q.n
c: Any = r.n
print(a is b, a is c, b is c)
fa: Any = p.f
fb: Any = q.f
print(fa is fb)
s = P(int("2000"), float("3.5"))
before: Any = s.n
t = copy.copy(s)
u = copy.deepcopy(s)
tn: Any = t.n
un: Any = u.n
print(before is tn, before is un)
