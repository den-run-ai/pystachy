# error: enum class SortKey's __new__() is not supported: its parameters are the class and the items of a member's value, by position
# CPython passes a member's value's items to a __new__ of any signature (printing calls)
from enum import StrEnum


class SortKey(StrEnum):
    CALLS = 'calls', 'ncalls'

    def __new__(cls, *values):
        value = values[0]
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj


print(SortKey.CALLS)
