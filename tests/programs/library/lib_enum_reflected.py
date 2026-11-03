# Comparisons of IntEnum and StrEnum members with objects of other classes: int's and str's methods
# return NotImplemented for them, so the other object's reflected method decides, or identity where
# it has none, as in CPython
from enum import Enum, IntEnum, StrEnum


class Number(IntEnum):
    ONE = 1
    TWO = 2


class Word(StrEnum):
    A = "a"


class Color(Enum):
    RED = 1


class Other:
    def __eq__(self, other: object) -> bool:
        print("Other.__eq__")
        return True

    def __gt__(self, other: object) -> bool:
        print("Other.__gt__")
        return True


class Plain:
    pass


print(Number.ONE == Other(), Number.ONE != Other(), Word.A == Other(), Word.A != Other())
print(Number.ONE < Other(), Word.A < Other())
print(Number.ONE == Plain(), Number.ONE != Plain(), Word.A == Plain())
print(Number.ONE == Word.A, Number.ONE == Color.RED, Word.A != Number.ONE)
print(Number.ONE == Number.ONE, Number.TWO > Number.ONE, Number.ONE == 1, Word.A == "a")
try:
    print(Number.ONE < Plain())
except TypeError as e:
    print("TypeError:", e)
