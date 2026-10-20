# error: inheritance from a NamedTuple is not supported
# _fields reads must not bypass the existing inheritance boundary or crash.
from typing import NamedTuple


class Point(NamedTuple):
    x: int
    y: int = 3


class Child(Point):
    pass


print(Child._fields, Child(4)._fields)
