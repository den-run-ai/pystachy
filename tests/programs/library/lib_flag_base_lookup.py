# A flag class's lookup and its in find a member held through a base class's type (Flag) or a union
# of member types, as CPython does; a member of another class raises CPython's TypeError for in
from enum import Enum, Flag


class Color(Enum):
    RED = 1


class Perm(Flag):
    R = 4
    W = 2


def reparse(x: Flag) -> Perm:
    return Perm(x)


def has(x: Flag) -> bool:
    return x in (Perm.R | Perm.W)


def has2(x: Perm | Color) -> bool:
    return x in (Perm.R | Perm.W)


print(reparse(Perm.R | Perm.W))
print(has(Perm.W), has2(Perm.W))
try:
    print(has2(Color.RED))
except TypeError as e:
    print("TypeError", e)
