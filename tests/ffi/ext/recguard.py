"""Recursion accounting survives exported-call exception boundaries (#988), and the native
stack's floor, set on the thread that imports the module, catches a recursion that its stack
cannot hold under a raised limit (#1015)."""
import sys
from ffi import export

_seen: list[float] = [0.0]


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


def _climb(n: int, a: float, b: float, c: float, d: float) -> float:
    # (unbounded; the work after the call keeps every frame on the stack, with the floats that
    # live across it: 300,000 frames need more than 8 MiB)
    if n == 100000000:
        return 0.0
    r = _climb(n + 1, a + 1.0, b + 2.0, c + 3.0, d + 4.0)
    _seen[0] = r
    return r + a + b + c + d


@export
def climb() -> float:
    return _climb(0, 0.0, 0.0, 0.0, 0.0)
