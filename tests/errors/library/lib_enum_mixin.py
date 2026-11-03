# error: enum class C is not supported: an enum class derives from one class
# CPython makes the members strs and enum members (printing C.A)
from enum import Enum


class C(str, Enum):
    A = "a"


print(C.A)
