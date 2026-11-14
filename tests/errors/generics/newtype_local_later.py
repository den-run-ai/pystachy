# error: newtype_local_later.py:10: error: local variable 'N' is read before its first assignment; declare it first (N: T)
# A function that assigns N makes N its local throughout: N(3) reads that local before it is
# bound (CPython's UnboundLocalError), not the module's NewType.
from typing import NewType

N = NewType("N", int)


def f() -> int:
    print(N(3))
    N = 1
    return N


print(f())
