# pystachy: dynamic-any
# An enum __new__'s numeric defaults in a module that opts in to dynamic Any.
from enum import Enum


class Coord(Enum):
    X = "x"
    Y = "y"

    def __new__(cls, label, scale=2.5, steps=4):
        obj = object.__new__(cls)
        obj._value_ = label
        obj.scale = scale
        obj.steps = steps
        return obj


for c in Coord:
    print(c, c.value, c.scale, c.steps)
