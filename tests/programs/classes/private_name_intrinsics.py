# Compiler-owned adapters keep their intrinsic calls inside class bodies. User code with
# the same spelling still follows CPython's lexical rules, for names, fields and methods.
from enum import Enum
from user_private import Imported


def _User__pys_range_len(value: int) -> int:
    return value + 2


class User:
    def __init__(self) -> None:
        self.__pys_value = 4

    def __pys_method(self, __pys_argument: int) -> int:
        return self.__pys_value + __pys_argument

    def run(self) -> int:
        return __pys_range_len(self.__pys_method(_User__pys_argument=3))


class Color(Enum):
    RED = 1
    BLUE = 2


u = User()
print(u.run(), u._User__pys_value)
print(Imported().read(_Imported__pys_local=3))
r = range(2, 11, 3)
print(len(r), bool(r), r[1], 8 in r)
it = iter("éx")
print(next(it), next(it))
print(Color(2).name)
