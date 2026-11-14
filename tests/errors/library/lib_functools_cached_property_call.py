# error: lib_functools_cached_property_call.py:10: error: cached_property(...) as a call is not supported: the compiler applies it where it decorates a method of a class statement (@cached_property)
from functools import cached_property


def compute(self) -> int:
    return 3


class A:
    v = cached_property(compute)


print(A().v)
