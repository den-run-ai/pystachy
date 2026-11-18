# TypeVars of an imported module (typevar_bound_forms) whose bound and constraints are typing's
# forms, as mypy's modules have them
from typing import Any, Callable, Optional, TypeVar

Fn = Callable[[int], Optional[int]]
F = TypeVar("F", bound=Callable[..., Any])
G = TypeVar("G", Fn, Optional[str])


def apply(f: F, n: int) -> int:
    return f(n)


def pick(x: Optional[str]) -> str:
    return "none" if x is None else x
