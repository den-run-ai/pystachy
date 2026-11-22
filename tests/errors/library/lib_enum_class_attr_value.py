# error: class attribute 'kind' of enum class Color is not supported: a variable or a field (self.kind = Color) may hold the class
# CPython's class attribute holds the enum class, through which Palette.kind.RED reads the member
from enum import Enum


class Color(Enum):
    RED = 1


class Palette:
    kind = Color


print(Palette.kind.RED)
