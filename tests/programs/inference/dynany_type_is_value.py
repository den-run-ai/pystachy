# pystachy: dynamic-any
# type(x) is type(y), for an Any x and a typed y whose type cannot become an Any value as a whole
# (an optional or a union with a list[int], bytes or tuple member), compares the type of the value
# y holds, as CPython does: NoneType's where it is None, list's for a list, and a union member's
# by its tag. Before, such a y's type compared as no type at all, and every comparison was False.
from typing import Any


def pick(k: int) -> int | list[int]:
    return 1 if k == 0 else [1]


none: Any = None
one: Any = 1
xs: Any = [5]
pair: Any = (1, [2])
y: list[int] | None = None
z: list[int] | None = [2]
print(type(none) is type(y), type(y) is type(none), type(none) == type(y), type(none) is not type(y))
print(type(xs) is type(z), type(none) is type(z), type(xs) is type(y), type(z) != type(xs))
b: bytes | None = None
bb: bytes | None = b"b"
print(type(none) is type(b), type(none) is type(bb), type(xs) is type(bb))
u = pick(0)
v = pick(1)
print(type(one) is type(u), type(one) is type(v), type(xs) is type(v), type(xs) is type(u))
t: tuple[int, list[int]] | None = (1, [2])
n: tuple[int, list[int]] | None = None
print(type(pair) is type(t), type(none) is type(t), type(none) is type(n), type(pair) is type(n))
