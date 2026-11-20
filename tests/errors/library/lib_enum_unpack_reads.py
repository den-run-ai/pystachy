# error: enum class C's A, B = ... is not supported: a value reads a name the statement binds
# CPython evaluates both values before it binds A, so B's value is the module's A (1), where binding
# the names in turn would read the member
from enum import Enum

A = 1


class C(Enum):
    A, B = 5, A


print(list(C))
