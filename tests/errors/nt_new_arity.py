# error: nt_new_arity.py:10: error: missing argument 'x' in call to P.__new__()
from typing import NamedTuple


class P(NamedTuple):
    x: int
    y: int = 0


print(P())
