# auto() counts from the values the class body assigns, not from the _value_ that __new__ gives
# the members.
from enum import Enum, auto


class Scaled(Enum):
    A = 1
    B = auto()
    C = auto()
    D = 7
    E = auto()

    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = value * 10
        return obj


for m in Scaled:
    print(m.name, m.value)
