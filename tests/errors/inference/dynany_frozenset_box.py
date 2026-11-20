# error: a frozenset[int] cannot become an Any value: Any values hold no sets yet (a list comprehension of its items can become one)
# pystachy: dynamic-any
# nor can a frozenset (#775, #1591; CPython prints 3)
from typing import Any


def size(x: Any) -> int:
    return len(x)


print(size(frozenset([1, 2, 3])))
