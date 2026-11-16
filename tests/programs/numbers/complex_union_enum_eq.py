# == and != of a union holding complex numbers and an IntEnum's or IntFlag's member, an int in
# CPython: each member compares the int as its own type does, so 1+0j equals the member whose
# value is 1; also in tuple search, and with None in the union
from enum import IntEnum, IntFlag


class E(IntEnum):
    ONE = 1


class F(IntFlag):
    A = 1
    B = 2


def numbers(v: int | complex) -> None:
    print(v == E.ONE, E.ONE == v, v != E.ONE, E.ONE != v, v == F.B, F.A != v)
    print(E.ONE in (v,), v in (E.ONE,), (v, 2j).count(E.ONE), (2j, v).index(F.A) if v == F.A else -1)


def maybe(v: float | complex | None) -> None:
    print(v == E.ONE, E.ONE == v, v != F.A, F.A in (v, 3j))


numbers(1)
numbers(1 + 0j)
numbers(2j)
maybe(None)
maybe(1.0)
maybe(1 + 0j)
maybe(1j)
