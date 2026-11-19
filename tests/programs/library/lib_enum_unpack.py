# Members bound together by unpacking (R, W, X = 4, 2, 1), as CPython's class namespace binds each
# name to its item in turn once the values are evaluated: aliases among them, auto() items (one
# more than the greatest value before), a list of values and a flag class's combination.
from enum import Enum, Flag, IntEnum, auto


class Perm(Flag):
    R, W, X = 4, 2, 1
    RW = R | W


class Color(Enum):
    RED, GREEN, ROJO = (1, 2, 1)
    BLUE, PINK = auto(), auto()


class Size(IntEnum):
    S, M = [1, 2]


print(list(Perm), Perm.RW, Perm(6), Perm.R.value)
print(list(Color), Color.ROJO is Color.RED, Color.PINK.value, list(Color.__members__))
print(list(Size), Size.M + 1)
