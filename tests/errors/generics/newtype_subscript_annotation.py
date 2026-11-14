# error: newtype_subscript_annotation.py:8: error: 'NewType' object is not subscriptable (CPython raises TypeError where it evaluates this annotation)
from typing import NewType, TypeVar

T = TypeVar("T")
N = NewType("N", list[T])


def f(x: N[int]) -> int:
    return len(x)


print(f(N([1, 2])))
