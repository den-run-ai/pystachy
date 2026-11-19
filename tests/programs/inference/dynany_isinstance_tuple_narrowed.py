# pystachy: dynamic-any
# isinstance(x, tuple) still narrows an Any local to a tuple in a program whose NamedTuple class
# is never boxed: tuple(x), which takes a tuple and no Any value, compiles as it did (#1581)
from typing import Any, NamedTuple


class P(NamedTuple):
    x: int
    y: int


def copied(v: Any) -> Any:
    if isinstance(v, tuple):
        return tuple(v)
    return None


def measured(v: Any) -> int:
    if not isinstance(v, (int, tuple)):
        return -1
    if isinstance(v, tuple):
        return len(tuple(v))
    return v


p = P(1, 2)  # (typed: no Any value holds it)
print(p.x + p.y, isinstance(p, tuple), p == (1, 2))
print(copied((1, "a")), copied([1]), copied(None), copied("ab"))
print(measured((1, 2, 3)), measured(7), measured("ab"), measured(()))
