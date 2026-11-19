# error: lib_enum_new_annotation_unbound.py:8: error: name 'Coord' is not defined (CPython evaluates this annotation when the def statement runs: quote it, or import annotations from __future__)
# An enum class's __new__ annotated with its own class, unquoted: CPython evaluates the
# annotation as the class body runs, before the name is bound, and raises NameError
from enum import IntEnum


class Coord(IntEnum):
    def __new__(cls, value) -> Coord:
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    X = 1


print(Coord.X.value)
