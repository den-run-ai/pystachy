# error: classvar_namedtuple.py:8: error: typing.ClassVar (a class attribute) is not supported
# (CPython's NamedTuple reads the annotation: TypeError: typing.ClassVar[int] is not valid as type argument)
from typing import ClassVar, NamedTuple


class Point(NamedTuple):
    x: int
    count: ClassVar[int] = 0


print(Point(1))
