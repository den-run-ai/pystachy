# pystachy: dynamic-any
# boundary= and @verify(...) name enum's FlagBoundary and EnumCheck members only as the compiler
# applies them, so their StrEnum classes are no classes of the program: an Enum value may become
# an Any value, and isinstance() of it and str is CPython's, as no StrEnum member may be one.
from enum import KEEP, UNIQUE, Enum, Flag, verify
from typing import Any


@verify(UNIQUE)
class Color(Enum):
    RED = 1


class Perm(Flag, boundary=KEEP):
    R = 1


def is_text(x: Enum) -> bool:
    return isinstance(x, str)


e: Enum = Color.RED
w: Any = e
print(is_text(Color.RED), w is e, repr(Perm(3)))
