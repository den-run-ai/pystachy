# error: flexible_alias_arity.py:9: error: mypy_extensions.FlexibleAlias takes two type arguments here, FlexibleAlias[T, X]: the alias's type variables, then the type it stands for
# A type alias's FlexibleAlias[...] takes exactly two type arguments, as mypy's stub declares
# it (CPython's object takes any number and keeps the last).
from typing import TypeVar

from mypy_extensions import FlexibleAlias

T = TypeVar("T")
Bogus = FlexibleAlias[T, T, int]


def f(x: Bogus[int]) -> int:
    return x


print(f(1))
