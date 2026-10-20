# error: nt_new_arity.py:10: error: P.__new__() missing 1 required positional argument: 'x'
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int = 0


print(P())
