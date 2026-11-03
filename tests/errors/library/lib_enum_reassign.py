# error: cannot reassign member 'A'
# CPython's AttributeError where the assignment runs
from enum import Enum


class C(Enum):
    A = 1
    B = 2


C.A = C.B
print(C.A)
