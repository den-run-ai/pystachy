# == and != of a complex number and an IntEnum's, an IntFlag's or an int mixin enum's member: the
# member is an int in CPython, whose int.__eq__ leaves the complex number to complex's, which
# compares the int; also in tuple search, and with members and complex numbers that may be None
from enum import Enum, IntEnum, IntFlag


class E(IntEnum):
    ONE = 1
    TWO = 2


class F(IntFlag):
    A = 1
    B = 2


class M(int, Enum):
    ONE = 1


def member(flag: bool) -> E | None:
    return E.ONE if flag else None


def number(flag: bool) -> complex | None:
    return complex(1, 0) if flag else None


z = complex(1, 0)
print(E.ONE == z, z == E.ONE, E.ONE != z, z != E.ONE, E.TWO == z, z != E.TWO)
print(F.A == z, z == F.A, F.A != z, z != F.A, (F.A | F.B) == 3 + 0j, F.B == 2j)
print(M.ONE == z, z == M.ONE, M.ONE != z, z != M.ONE)
print(E.ONE in (z,), z in (E.ONE,), (z, 2j).count(E.ONE), (E.TWO, E.ONE).index(z), F.A in (1j, z))
for fm in [False, True]:
    for fn in [False, True]:
        e = member(fm)
        c = number(fn)
        print(fm, fn, e == c, c == e, e != c, c != e)
