# error: nt_hash.py:10: error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not Pair (a NamedTuple, which CPython hashes as the tuple of its fields)
from typing import NamedTuple


class Pair(NamedTuple):
    a: int
    b: int


seen = {Pair(1, 2): True}
