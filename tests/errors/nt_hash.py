# error: nt_hash.py:10: error: dict keys must be int or str
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int


seen = {Pair(1, 2): True}
