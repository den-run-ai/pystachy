# pystachy: dynamic-any
# a builtin method, a class's method or a function called through an Any value with a keyword
# argument twice, which ** brings: the arguments are evaluated, then TypeError, before the
# callee runs or changes anything, as CPython merges them (#826)
from typing import Any


def side(n: int) -> int:
    print("side", n)
    return n


d: Any = {"z": 0}
try:
    d.update(a=side(1), **{"a": side(2)})
except TypeError as e:
    print("TypeError", e)
print(d)
try:
    d.update({"y": side(3)}, b=side(4), **{"c": side(5), "b": side(6)})
except TypeError as e:
    print("TypeError", e)
print(d)
xs: Any = [3, 1, 2]
try:
    xs.sort(reverse=bool(side(1)), **{"reverse": False})
except TypeError as e:
    print("TypeError", e)
print(xs)
try:
    xs.append(a=side(7), **{"a": side(8)})
except TypeError as e:
    print("TypeError", e)
print(xs)
d.update(e=side(9), **{"f": side(10)})
print(d)


def g(**kw: int) -> int:
    print("g ran")
    return len(kw)


def h(a: int) -> int:
    print("h ran")
    return a


class C:
    def m(self, **kw: int) -> int:
        print("m ran")
        return len(kw)


f: Any = g
try:
    f(a=side(11), **{"a": side(12)})
except TypeError as e:
    print("TypeError", e)
f = h
try:
    f(a=side(13), **{"a": side(14)})
except TypeError as e:
    print("TypeError", e)
c: Any = C()
try:
    c.m(a=side(15), **{"a": side(16)})
except TypeError as e:
    print("TypeError", e)
f = g
print(f(a=side(17), **{"b": side(18)}))
