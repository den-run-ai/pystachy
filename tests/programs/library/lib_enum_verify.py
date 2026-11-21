# @verify(UNIQUE, CONTINUOUS, NAMED_FLAGS) of enum classes whose checks pass (a flag's aliases of
# named bits, an enum's negative values, checks given as EnumCheck's members), and verify(...)
# and unique() called on a class: they check the class as a value and raise CPython's
# ValueError, or TypeError where CONTINUOUS meets values that are no ints.
import enum
from enum import CONTINUOUS, NAMED_FLAGS, UNIQUE, Enum, EnumCheck, Flag, IntEnum, IntFlag, auto, unique, verify


@verify(UNIQUE, CONTINUOUS)
class Auto(Enum):
    FIRST = auto()
    SECOND = auto()
    THIRD = auto()


@enum.verify(enum.CONTINUOUS)
class Manual(IntEnum):
    FIRST = 3
    SECOND = 4
    THIRD = 5


@verify(EnumCheck.NAMED_FLAGS, CONTINUOUS)
@unique
class Perm(Flag):
    R = 1
    W = 2
    X = 4
    RW = 3
    ALL = 7
    NONE = 0


@verify(NAMED_FLAGS)
class Signed(Enum):
    LOW = -3
    HIGH = 4
    TOP = 4


@verify()
class Empty(Enum):
    ONLY = "x"


class Gaps(Enum):
    A = 1
    B = 4
    C = 4


class Bits(IntFlag):
    b = 3
    c = 4
    d = 6


class Words(Enum):
    A = "a"
    B = "b"


print(list(Auto), list(Manual), list(Perm), repr(Perm.RW), list(Signed), Signed.TOP, list(Empty))
print(verify(UNIQUE, CONTINUOUS)(Auto), verify(NAMED_FLAGS)(Perm), unique(Manual))
for check in [UNIQUE, CONTINUOUS, NAMED_FLAGS]:
    try:
        verify(check)(Gaps)
        print(check.name, "passes")
    except ValueError as e:
        print(check.name, "ValueError", e)
try:
    unique(Gaps)
except ValueError as e:
    print("ValueError", e)
try:
    verify(NAMED_FLAGS)(Bits)
except ValueError as e:
    print("ValueError", e)
try:
    verify(CONTINUOUS)(Words)
except TypeError as e:
    print("TypeError", e)
print(verify(UNIQUE, NAMED_FLAGS)(Words), list(Bits))
