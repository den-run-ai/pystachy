# error: nt_make.py:10: error: P._make() is not supported: call P(...) with the fields
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int


print(P._make([1, 2]))
