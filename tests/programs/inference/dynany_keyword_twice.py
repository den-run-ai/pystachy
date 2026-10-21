# pystachy: dynamic-any
# a builtin method called through an Any value with a keyword argument twice, which ** brings:
# the arguments are evaluated, then TypeError, before the method changes anything, as CPython
# merges them (#826)
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
