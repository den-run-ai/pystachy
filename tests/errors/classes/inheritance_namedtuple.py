# error: inheritance from a NamedTuple is not supported
from typing import NamedTuple


class P(NamedTuple):
    x: int


class Q(P):
    pass


print(Q(1).x)
