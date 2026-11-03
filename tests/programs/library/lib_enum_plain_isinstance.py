# pystachy: dynamic-any
# Plain Enum classes beside the int- and str-like ones' rules: with no IntEnum, StrEnum or mixed-in
# class, isinstance() of an Enum value and int, and an Enum value as an Any value, are as CPython's
from enum import Enum
from typing import Any
class Color(Enum):
    RED = 1
def is_integer(x: Enum) -> bool:
    return isinstance(x, int)
v: Any = Color.RED
e: Enum = Color.RED
w: Any = e
print(is_integer(Color.RED), isinstance(v, int), w is v)
