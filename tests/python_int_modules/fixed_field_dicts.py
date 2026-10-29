# A module that does not opt in: its NamedTuple's and object's tuple fields hold 64-bit ints, -2**63 among them.
from typing import NamedTuple


class Pair(NamedTuple):
    a: tuple[int, int]
    b: tuple[int, int]


class Obj:
    def __init__(self) -> None:
        self.x = (1, -9223372036854775807 - 1)
        self.y = (2, 3)


def made() -> Pair:
    return Pair((1, -9223372036854775807 - 1), (2, 3))


def obj() -> Obj:
    return Obj()
