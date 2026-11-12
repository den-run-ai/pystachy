# error: enum member Code.A is not supported: __new__() makes it of another value than its _value_
# CPython's IntEnum member is the int its __new__ makes it of, whatever its _value_ (printing 2 1)
from enum import IntEnum


class Code(IntEnum):
    A = 1

    def __new__(cls, value):
        obj = int.__new__(cls, value + 1)
        obj._value_ = value
        return obj


print(Code.A + 0, Code.A.value)
