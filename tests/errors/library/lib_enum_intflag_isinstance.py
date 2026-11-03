# error: isinstance() of a I member and int is not supported: an IntFlag member is an object of its class (in CPython also an int)
# CPython's IntFlag member is an int (printing True)
from enum import IntFlag


class I(IntFlag):
    A = 1


print(isinstance(I.A, int))
