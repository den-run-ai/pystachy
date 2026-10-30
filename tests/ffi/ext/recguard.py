"""Recursion accounting survives exported-call exception boundaries (#988)."""
import sys
from ffi import export


@export
def set_limit(n: int) -> None:
    sys.setrecursionlimit(n)


@export
def get_limit() -> int:
    return sys.getrecursionlimit()


def _depth(n: int) -> int:
    if n == 0:
        return 0
    return 1 + _depth(n - 1)


def _fail(n: int) -> None:
    if n == 0:
        raise ValueError("bounded")
    _fail(n - 1)


@export
def depth(n: int) -> int:
    return _depth(n)


@export
def fail(n: int) -> None:
    _fail(n)
