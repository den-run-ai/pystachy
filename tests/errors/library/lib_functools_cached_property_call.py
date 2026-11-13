# error: lib_functools_cached_property_call.py:10: error: cannot infer the type of class attribute 'v'; annotate it (v: T = ...)
from functools import cached_property


def compute(self) -> int:
    return 3


class A:
    v = cached_property(compute)


print(A().v)
