# error: isinstance() of a Enum value, which may be a Number member, and int is not supported: an IntEnum member is an object of its class (in CPython also an int)
# An Enum-typed value may hold an IntEnum member, of which CPython's isinstance(x, int) is true
from enum import Enum, IntEnum


class Number(IntEnum):
    ONE = 1


def is_integer(x: Enum) -> bool:
    return isinstance(x, int)


print(is_integer(Number.ONE))
