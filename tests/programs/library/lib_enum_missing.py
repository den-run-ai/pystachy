# An enum class's _missing_() class method: a lookup by a value no member has calls it, and returns
# the member it returns, raises CPython's ValueError where it returns None, and passes on an
# exception it raises (a case-insensitive lookup is the common use)
from enum import Enum, IntEnum, StrEnum
class M(Enum):
    RED = 1
    GREEN = 2
    @classmethod
    def _missing_(cls, value):
        print("missing", repr(value))
        if value == 99:
            return cls.RED
        return None
print(M(99), M(1), M(M.GREEN))
try:
    M(5)
except ValueError as e:
    print("ValueError", e)
class Color(StrEnum):
    RED = "red"
    BLUE = "blue"
    @classmethod
    def _missing_(cls, value):
        for member in cls:
            if member.value == value.lower():
                return member
        return None
print(repr(Color("RED")), repr(Color("Blue")), repr(Color("blue")))
try:
    Color("green")
except ValueError as e:
    print("ValueError", e)
class Level(IntEnum):
    LOW = 1
    HIGH = 2
    @classmethod
    def _missing_(cls, value):
        raise KeyError(value)
try:
    Level(7)
except KeyError as e:
    print("KeyError", e)
