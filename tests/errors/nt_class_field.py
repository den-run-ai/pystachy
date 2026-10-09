# error: reading a NamedTuple's field through its class (P.x, a descriptor in CPython) is not supported
from typing import NamedTuple


class P(NamedTuple):
    x: int = 3


print(P.x)
