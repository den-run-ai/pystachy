# error: auto() after a member whose value is written as a tuple
# auto() counts from the values as written: CPython cannot increment a tuple (TypeError).
from enum import Enum, auto


class Pair(Enum):
    A = (1, 2)
    B = auto()

    def __new__(cls, value, extra=0):
        obj = object.__new__(cls)
        obj._value_ = value + extra
        return obj


print(list(Pair))
