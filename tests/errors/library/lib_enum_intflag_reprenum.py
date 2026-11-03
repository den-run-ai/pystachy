# error: isinstance() of a I member and ReprEnum is not supported: an IntFlag class derives from Flag here, where CPython's derives from ReprEnum too
# CPython's IntFlag(int, ReprEnum, Flag) member is a ReprEnum (printing True)
from enum import IntFlag, ReprEnum


class I(IntFlag):
    A = 1


print(isinstance(I.A, ReprEnum))
