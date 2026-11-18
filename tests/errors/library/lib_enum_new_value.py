# error: enum member Size.SMALL is not supported: the compiler computes the _value_ that __new__() gives a member
# CPython runs __new__ as the class body ends, so a member's _value_ is any value it computes
# (printing Size.SMALL 5)
from enum import Enum


class Size(Enum):
    SMALL = "small"

    def __new__(cls, label):
        obj = object.__new__(cls)
        obj._value_ = len(label)
        return obj


print(Size.SMALL, Size.SMALL.value)
