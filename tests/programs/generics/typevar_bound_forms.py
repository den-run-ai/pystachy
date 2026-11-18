# What CPython's TypeVar accepts as its bound and constraints, which Pystachy does not evaluate:
# Any and a plain Callable; a plain special form such as Union as a constraint, which TypeVar does
# not check as it checks a bound, or as an argument of a builtin class's subscript, which checks
# none; typing's subscripts of types, and '|' of them. mods.tvforms has such TypeVars of an
# imported module, as mypy's are.
import typing
from collections.abc import Callable
from typing import Any, Dict, NoReturn, Optional, Tuple, TypeVar, Union

from mods.tvforms import apply, pick

A = TypeVar("A", bound=Any)
B = TypeVar("B", bound=Callable)
H = TypeVar("H", int, Union)
I = TypeVar("I", bound=Optional[int] | Dict[str, int])
J = TypeVar("J", Tuple[int, ...], list[Union], tuple[()])
K = TypeVar("K", bound=typing.Callable[[int, list[Union]], NoReturn])
L = TypeVar("L", bound=None | int)


def first(xs: list[A]) -> A:
    return xs[0]


def double(n: int) -> int:
    return n * 2


print(first([1, 2]), first(["a"]), apply(double, 4), pick(None), pick("s"))
