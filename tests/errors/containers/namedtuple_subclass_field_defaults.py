# error: inheritance from a NamedTuple is not supported
# _field_defaults reads through a namedtuple subclass also reject cleanly.
from collections import namedtuple

Point = namedtuple("Point", "x y", defaults=[3])


class Child(Point):
    pass


print(Child._field_defaults, Child(4)._field_defaults)
