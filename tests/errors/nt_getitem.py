# error: nt_getitem.py:5: error: a NamedTuple that defines __getitem__ is not supported (Pystachy reads its fields where CPython would call it)
from typing import NamedTuple


class P(NamedTuple):
    x: int

    def __getitem__(self, i: int) -> int:
        return 100 + i


print(P(1)[0])
