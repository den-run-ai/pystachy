# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a concrete annotation that receives an Any value checks the value's type where it is
# unboxed, and raises TypeError where CPython, which does not check annotations, goes on (here
# it would print abab).
# pystachy: dynamic-any
from typing import Any


def double(n: int) -> int:
    return n * 2


v: Any = 21
print(double(v))
v = "ab"
print(double(v))
