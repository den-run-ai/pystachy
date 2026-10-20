# tuples (and NamedTuples) whose items are ints, floats or bools compare with tuples whose items
# may be None, either way round, as CPython compares them
from typing import NamedTuple


class P(NamedTuple):
    a: int | None
    b: float | None = None


def gp(flag: bool) -> P | None:
    return P(1, 2.0) if flag else None


t: tuple[int | None, int] = (1, 2)
u: tuple[int, int] = (1, 2)
n: tuple[int | None, int] = (None, 2)
print(P(1) == (1, None), P(1, 2.0) == (1, 2.0), (1, 2.0) == P(1, 2.0), P(None) != (1, None))
print((1, 2) == t, t == (1, 2), t == u, u == t, u != n, n == (None, 2), (1, 2) <= t, u < t, t > (0, 5))
print(gp(True) == (1, 2.0), gp(False) == (1, 2.0), (1, 2.0) == gp(True), ((1, True), "a") == ((1, None), "a"))
print(((1, 2), 3) == ((t[0], 2), 3), (1, None) == (1, 2), (None, 2) == u)
print(u < n)
