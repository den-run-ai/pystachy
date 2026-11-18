# == and != of a complex number and an IntEnum member whose class defines its own __eq__ or
# __ne__: with the member on the left its method answers; with the complex number on the left,
# complex's comparison takes the member as the int it is. A class with its own __eq__ alone still
# gets int's __ne__, which leaves a complex number to complex's
from enum import IntEnum


class Both(IntEnum):
    ONE = 1

    def __eq__(self, other: complex) -> bool:
        return True

    def __ne__(self, other: complex) -> bool:
        return False


class EqOnly(IntEnum):
    ONE = 1

    def __eq__(self, other: complex) -> bool:
        return True


z = 2j
print(Both.ONE == z, Both.ONE != z, z == Both.ONE, z != Both.ONE)
print((Both.ONE,).count(z), z in (Both.ONE,), Both.ONE in (z,))
print(EqOnly.ONE == z, EqOnly.ONE != z, z == EqOnly.ONE, z != EqOnly.ONE)
print(EqOnly.ONE == 1 + 0j, EqOnly.ONE != 1 + 0j)
