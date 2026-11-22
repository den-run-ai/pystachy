# error: 'X' already defined as 2
# CPython's TypeError where the class body binds a member's name that a nonmember() has
from enum import Enum, nonmember


class C(Enum):
    A = 1
    X = nonmember(2)
    X = 3


print(C.X)
