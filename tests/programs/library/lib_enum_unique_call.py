# unique() called on an enum class, not as the decorator of its class statement: CPython checks
# the class it is given, here its EnumType object, and raises ValueError for its aliases (a
# flag class's repr() is <flag 'Perm'>), else returns the class.
from enum import Enum, Flag, unique


class Gaps(Enum):
    A = 1
    B = 4
    C = 4


class Perm(Flag):
    R = 1
    W = 2
    RW = 3
    BOTH = 3


class Clean(Enum):
    X = 1


print(unique(Clean), list(unique(Clean)))
try:
    unique(Gaps)
    print("no error")
except ValueError as e:
    print("ValueError", e)
try:
    unique(Perm)
    print("no error")
except ValueError as e:
    print("ValueError", e)
