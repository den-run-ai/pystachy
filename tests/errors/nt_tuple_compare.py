# error: nt_tuple_compare.py:9: error: comparing a NamedTuple with a tuple (Pair == tuple[int,int]) is not supported
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int

print(Pair(1, 2) == (1, 2))
