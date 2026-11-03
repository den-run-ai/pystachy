# error: isinstance() of a N member and int is not supported
# CPython's IntEnum member is also an int (printing True)
from enum import IntEnum


class N(IntEnum):
    A = 1


print(isinstance(N.A, int))
