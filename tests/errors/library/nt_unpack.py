# error: nt_unpack.py:10: error: cannot unpack Pair (2 fields) into 3 targets
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int


a, b, c = Pair(1, 2)
