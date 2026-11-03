# error: isinstance() of a N member and IntEnum is not supported: an enum class of int and Enum derives from IntEnum here, where CPython's derives from Enum only
# CPython's class N(int, Enum) is no IntEnum (printing False)
from enum import Enum, IntEnum


class N(int, Enum):
    ONE = 1


print(isinstance(N.ONE, IntEnum))
