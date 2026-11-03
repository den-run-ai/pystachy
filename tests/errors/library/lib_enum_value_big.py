# error: enum member V.B is not supported: the compiler makes an enum class's members from literal values
# A computed value past the 64-bit int range, which CPython computes (printing 9223372036854775808)
from enum import Enum


class V(Enum):
    A = 1 << 62
    B = A * 2


print(V.B.value)
