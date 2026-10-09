# error: nt_star_unpack.py:10: error: starred expressions (*x) are not supported
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int
    z: int

a, *rest = P(1, 2, 3)
print(a, rest)
