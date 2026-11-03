# error: enum member V.A is not supported: the compiler makes an enum class's members from literal values
# A module name bound twice is no constant here: the class body reads its value at that point (2)
from enum import Enum

BASE = 1
BASE = 2


class V(Enum):
    A = BASE


print(V.A.value)
