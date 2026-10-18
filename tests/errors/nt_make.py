# error: nt_make.py:10: error: P._make() of a tuple of 1 item is not supported: it raises TypeError: Expected 2 arguments, got 1
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int


print(P._make((1,)))
