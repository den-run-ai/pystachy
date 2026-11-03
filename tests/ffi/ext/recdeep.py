"""An extension module that CPython calls from deeper in its thread's native stack than the import
was, directly and from a Python callback that the module makes itself (#1015,
tests/ffi/ext/recdeepclient.py)."""
import sys
from ffi import export
from pyobj import import_module, of_int

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


@export
def depth(n: int) -> int:
    return _depth(n)


def _climb(n: int, a: float, b: float) -> float:
    # (unbounded; the work after the call keeps every frame on the stack)
    if n == 100000000:
        return 0.0
    r = _climb(n + 1, a + 1.0, b + 2.0)
    _seen[0] = r
    return r + a + b


@export
def climb() -> float:
    return _climb(0, 0.0, 0.0)


@export
def through(name: str, n: int) -> int:
    # (calls the client's function name with n, which may call this module again, from deeper in
    # the stack; a later shallow recursion verifies that unwinding restored the active depth)
    r = import_module("__main__").attr(name).call([of_int(n)]).to_int()
    return r + _depth(10)
