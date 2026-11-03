# error: enum class M's _missing_() is supported as a class method (@classmethod)
# EnumType calls _missing_ on the class: as a plain method, CPython's call lacks its value argument
from enum import Enum


class M(Enum):
    RED = 1

    def _missing_(self, value):
        return None


print(M(1))
