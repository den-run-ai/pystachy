# error: a I member cannot become an Any value: an IntFlag member is an object of its class, where CPython's is also an int
# pystachy: dynamic-any
# An Any value of an IntFlag member would answer isinstance(v, int) as no int, where CPython's is one
from enum import IntFlag
from typing import Any


class I(IntFlag):
    A = 1


v: Any = I.A
print(isinstance(v, int))
