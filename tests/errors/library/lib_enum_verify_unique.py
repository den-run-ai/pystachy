# error: aliases found in <enum 'Dirtier'>: double -> single, turkey -> triple
# CPython's ValueError where @verify(UNIQUE) runs, as the class statement ends
from enum import UNIQUE, IntEnum, verify


@verify(UNIQUE)
class Dirtier(IntEnum):
    single = 1
    double = 1
    triple = 3
    turkey = 3


print(list(Dirtier))
