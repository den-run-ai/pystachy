# error: enum class C is not supported: an enum class derives from one class
# A mixin type other than str and int: CPython makes the members floats and enum members (printing C.A)
from enum import Enum


class C(float, Enum):
    A = 1.5


print(C.A)
