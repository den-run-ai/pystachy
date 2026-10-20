# error: nt_new.py:5: error: Cannot overwrite NamedTuple attribute __new__
from typing import NamedTuple


class P(NamedTuple):
    x: int

    def __new__(cls, x: int) -> "P":
        return super().__new__(cls, x)


print(P(1))
