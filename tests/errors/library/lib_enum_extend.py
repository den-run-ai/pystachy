# error: <enum 'D'> cannot extend <enum 'C'>
# CPython's TypeError where the class statement runs
from enum import Enum


class C(Enum):
    A = 1


class D(C):
    B = 2


print(D.B)
