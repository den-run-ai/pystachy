# error: enum member Level.HIGH is not supported: the compiler makes an enum class's members from literal values
# In a class that @_simple_enum makes an enum class of, a name bound to auto() is an auto object
# until the decorator runs: CPython's TypeError for auto + 1, where the class body runs
from enum import IntEnum, auto, _simple_enum


@_simple_enum(IntEnum)
class Level:
    LOW = auto()
    HIGH = LOW + 1


print(Level.HIGH)
