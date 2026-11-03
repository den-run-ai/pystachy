# error: enum class M's _missing_() returns a int: CPython's lookup raises TypeError for a result other than a member of the class or None
# CPython raises TypeError: error in M._missing_: returned 3 instead of None or a valid member
from enum import Enum


class M(Enum):
    RED = 1

    @classmethod
    def _missing_(cls, value):
        return 3


print(M(7))
