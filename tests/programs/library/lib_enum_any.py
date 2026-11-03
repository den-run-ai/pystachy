# pystachy: dynamic-any
# enum members in Any values: isinstance(), equality, identity and repr() as for typed values
from enum import Enum, IntEnum
from typing import Any


class Color(Enum):
    RED = 1
    GREEN = 2


class Num(IntEnum):
    ONE = 1


def show(v: Any) -> str:
    if isinstance(v, Color):
        return "color " + v.name
    return "other " + repr(v)


# (an IntEnum member is no Any value, as it is an int in CPython: its value is)
items: list[Any] = [Color.RED, 3, "x", Color.GREEN, Num.ONE.value]
print([show(v) for v in items])
print(items[0] == Color.RED, items[0] is Color.RED, items[3] != Color.RED)
print(items)
print(Color(items[1] - 1))
