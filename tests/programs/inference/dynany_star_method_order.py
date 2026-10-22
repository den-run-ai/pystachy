# pystachy: dynamic-any
# o.m(*t, **d) of an Any o: the method is looked up before the unpacked arguments are evaluated,
# as CPython's LOAD_ATTR looks it up, so a missing method raises first (#826)
from typing import Any


def side(s: str) -> int:
    print("evaluated", s)
    return 1


class C:
    def m(self, a: int, k: int = 0) -> int:
        return a + k


x: Any = C()
try:
    x.nope(**{"k": side("dstar")})
except AttributeError:
    print("AttributeError")
try:
    x.nope(*(side("star"), 2))
except AttributeError:
    print("AttributeError")
print(x.m(*(side("a"),), **{"k": side("k")}))
