# pystachy: dynamic-any
# A dict of Any values holds its keys as boxes too (dynany_layout_keys): so do the dicts that
# _asdict() and a copy of vars() make of fields that hold Any values (#821).
from typing import Any, NamedTuple


class P(NamedTuple):
    a: Any
    b: Any


class C:
    def __init__(self) -> None:
        self.a: Any = 1
        self.b: Any = [2, "x"]


p = P(1, ["two"])
d = p._asdict()
print(d, d["b"][0], d["b"] is p.b)
d["c"] = 3
print(sorted(d))
c = C()
e = dict(vars(c))
print(e, e["b"] is c.b)
f = vars(c).copy()
f["a"] = "changed"
print(f, c.a)
