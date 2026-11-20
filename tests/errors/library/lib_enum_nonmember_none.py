# error: enum class C's nonmember N is not supported: its value is a literal
# A class attribute of None has no type here (CPython prints None)
from enum import Enum, nonmember


class C(Enum):
    A = 1
    N = nonmember(None)


print(C.N)
