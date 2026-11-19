# error: enum member Bumped.A is not supported: the compiler computes the _value_ that __new__() gives a member
# A parameter that __new__ rebinds with another statement than NAME = value (value += 1) holds no
# value the compiler computes: CPython's member has the value 2.
from enum import Enum


class Bumped(Enum):
    A = 1
    B = 5

    def __new__(cls, value):
        obj = object.__new__(cls)
        value += 1
        obj._value_ = value
        return obj


for m in Bumped:
    print(m.name, m.value)
print(Bumped(2), Bumped(6))
