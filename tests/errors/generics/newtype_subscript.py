# error: newtype_subscript.py:6: error: 'NewType' object is not subscriptable (CPython evaluates this NewType's type when the assignment runs)
from typing import NewType, TypeVar

T = TypeVar("T")
N = NewType("N", list[T])
M = NewType("M", N[int])
print(M([1]))
