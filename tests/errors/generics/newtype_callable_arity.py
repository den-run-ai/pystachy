# error: newtype_callable_arity.py:4: error: Callable must be used as Callable[[arg, ...], result] (CPython evaluates this NewType's type when the assignment runs)
from typing import Callable, NewType

N = NewType("N", Callable[int])
print(N(3))
