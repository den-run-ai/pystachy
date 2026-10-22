# pystachy: dynamic-any
# ** mappings merge in order. A duplicate stops later groups, but repeated keys inside one
# display keep the last value at the first position. Empty strings are valid keyword names.
from typing import Any


def side(n: int) -> int:
    print("side", n)
    return n


def g(**kw: int) -> int:
    print("g", kw)
    return len(kw)


class C:
    def m(self, **kw: int) -> int:
        print("m", kw)
        return len(kw)


f: Any = g
try:
    f(a=side(1), **{"a": side(2)}, b=side(3))
except TypeError as e:
    print("duplicate", e)
# All the values of one display run before its merge can fail.
try:
    f(a=side(4), **{"a": side(5), "b": side(6)}, **{"c": side(7)})
except TypeError as e:
    print("mapping", e)
# Consecutive explicit keywords are one mapping, too.
try:
    f(**{"a": side(8)}, a=side(9), b=side(10), **{"c": side(11)})
except TypeError as e:
    print("keywords", e)
print(f(**{"a": side(12), "b": side(13), "a": side(14)}))
try:
    f(**{"": side(15)}, **{"": side(16)}, later=side(17))
except TypeError as e:
    print("empty", e)
c: Any = C()
try:
    c.m(**{"": side(18)}, **{"": side(19)}, later=side(20))
except TypeError as e:
    print("method", e)
print(c.m(**{"a": side(21), "a": side(22)}))
d: Any = {"z": 0}
try:
    d.update(**{"": side(23)}, **{"": side(24)}, later=side(25))
except TypeError as e:
    print("builtin", e)
print(d)
d.update(**{"a": side(26), "a": side(27)})
print(d)
# Lookup still precedes evaluation, even when the call would have duplicate keywords.
try:
    c.missing(**{"a": side(28)}, **{"a": side(29)})
except AttributeError:
    print("missing")
