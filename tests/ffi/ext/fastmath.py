"""Numeric helpers: run by CPython as they are, or compiled by `pystachy ext` into fastmath.abi3.so"""
import sys
from ffi import export

_calls = 0


@export
def fib(n: int) -> int:
    global _calls
    _calls += 1
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@export
def check(n: int) -> int:
    if n < 0:
        raise ValueError(f"negative: {n}")
    return n * 2


@export
def shout(s: str) -> str:
    return s.upper() + "!"


@export
def words(s: str) -> int:
    counts: dict[str, int] = {}
    for w in s.split():
        counts[w] = counts.get(w, 0) + 1
    return len(counts)


@export
def hello(name: str) -> None:
    print("hello from Pystachy,", name)


@export
def ncalls() -> int:
    return _calls


@export
def bye(code: int) -> None:
    sys.exit(code)


class _TooBig(ValueError):
    pass


@export
def big(n: int) -> int:
    if n > 90:
        raise _TooBig("fib(" + str(n) + ") does not fit in 64 bits")
    return n


def _helper(xs: list[int]) -> int:
    return sum(xs)


print("fastmath ready")


@export
def lookup(k: str) -> int:
    d = {"a": 1}
    return d[k]


@export
def bad2(n: int) -> int:
    raise ValueError("bad", n)


@export
def quit_msg(s: str) -> None:
    sys.exit(s)


@export
def empty() -> None:
    raise ValueError()


@export
def quit_none(n: int) -> None:
    sys.exit()


@export
def scale(x: float, neg: bool) -> float:
    return -x if neg else x * 2


@export
def width(text: str) -> int:
    return len(text)
