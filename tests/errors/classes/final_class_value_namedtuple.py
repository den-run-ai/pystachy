# error: final_class_value_namedtuple.py:7: error: a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]
# (CPython's NamedTuple reads the annotation: TypeError: Plain typing.Final is not valid as type argument)
from typing import Final, NamedTuple


class Point(NamedTuple):
    x: Final = (1, 2)


print(Point())
