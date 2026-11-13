# error: enum class Pair's __new__() is not supported: @_simple_enum(Enum) calls it without the member's value
# CPython's _simple_enum(Enum) calls the class's __new__ with the class alone: TypeError here,
# where the decorator runs
from enum import Enum, _simple_enum


@_simple_enum(Enum)
class Pair:
    A = (1, 2)

    def __new__(cls, a, b):
        obj = object.__new__(cls)
        obj.first = a
        return obj


print(Pair.A.first)
