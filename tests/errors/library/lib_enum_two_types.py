# error: enum class C's members have values of two types, int and str
# CPython's members' values may have any types (printing C.B)
from enum import Enum


class C(Enum):
    A = 1
    B = "b"


print(C.B)
