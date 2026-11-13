# A name that __new__ reads is the module's constant, also where a member before has that name:
# a class body's names are no names of a function in it.
from enum import Enum

BASE = 10
STEP = 100


class Shadow(Enum):
    BASE = 1
    A = 2

    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = value + BASE + STEP
        return obj


for m in Shadow:
    print(m.name, m.value)
