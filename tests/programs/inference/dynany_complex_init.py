# pystachy: dynamic-any
# x.__init__(...) of a complex number held as an Any value is object.__init__, as a typed one's is
# (complex_init_noop.py): its arguments are evaluated and ignored, and it returns None.
from typing import Any


def note(v: int, seen: list[str]) -> int:
    seen.append(str(v))
    return v


seen: list[str] = []
x: Any = 1 + 2j
alias = x
print(x.__init__(), x.__init__(note(5, seen), "a", key=note(6, seen)))
print(x, alias, seen, x == alias, hash(x) == hash(1 + 2j))
