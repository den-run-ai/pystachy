# An enum class's __new__ may annotate its return, as the member it makes (#1555): the compiler
# makes the members as for an unannotated __new__, in an IntEnum, an Enum and an (int, Enum)
# class, with annotated parameters too.
from enum import Enum, IntEnum


class Coord(IntEnum):
    def __new__(cls, value) -> "Coord":
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    X = 1
    Y = 2


class Label(Enum):
    def __new__(cls, value: int, text: str = "") -> "Label":
        obj = object.__new__(cls)
        obj._value_ = value
        obj.text = text
        return obj

    A = 1, "first"
    B = 2


class Mixed(int, Enum):
    def __new__(cls, value: int) -> "Mixed":
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj

    P = 10
    Q = 20


print(Coord.Y.value, Coord(1).name, Coord.X + 1, list(Coord))
print(Label.A.value, repr(Label.A.text), repr(Label.B.text), Label(2).name)
print(Mixed.Q.value, Mixed.P + Mixed.Q, Mixed(10) is Mixed.P, [m.name for m in Mixed])
