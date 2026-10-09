# error: nt_iterate.py:10: error: iterating over a NamedTuple (Pair) is not supported: unpack it, or read its fields
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int


for x in Pair(1, 2):
    print(x)
