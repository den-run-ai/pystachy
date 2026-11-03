# error: duplicate values found in <enum 'C'>: B -> A
# CPython's ValueError where @unique runs
from enum import Enum, unique


@unique
class C(Enum):
    A = 1
    B = 1


print(C.B)
