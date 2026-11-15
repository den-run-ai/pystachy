# pystachy: python-int
from enum import IntEnum


class Number(IntEnum):
    ONE = 1

    def __eq__(self, other) -> bool:
        print("eq")
        return NotImplemented

    def __lt__(self, other) -> bool:
        print("lt")
        return NotImplemented


for value in (1, 2 ** 70, -2 ** 70):
    print(Number.ONE == value, value == Number.ONE, Number.ONE < value, value > Number.ONE)
    print(Number.ONE in (value,), value in (Number.ONE,))
