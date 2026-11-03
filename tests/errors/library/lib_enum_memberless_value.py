# error: enum class Base without members cannot be used as a value
# CPython iterates over no members (printing [])
from enum import Enum


class Base(Enum):
    pass


print(list(Base))
