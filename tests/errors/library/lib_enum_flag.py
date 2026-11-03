# error: enum class P is not supported: an enum class derives from one class, Enum, IntEnum, StrEnum, Flag, IntFlag
# A flag class's boundary keyword: Pystachy's Flag keeps STRICT and IntFlag KEEP (CPython's CONFORM drops bit 8, printing <P.A: 1>)
from enum import CONFORM, Flag


class P(Flag, boundary=CONFORM):
    A = 1


print(repr(P(9)))
