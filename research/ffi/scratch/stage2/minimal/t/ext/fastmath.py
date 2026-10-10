"""Numeric helpers: run by CPython as they are, or compiled by `pystachy ext` into fastmath.abi3.so"""
import sys

calls = 0


def fib(n: int) -> int:
    global calls
    calls += 1
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def check(n: int) -> int:
    if n < 0:
        raise ValueError(f"negative: {n}")
    return n * 2


def shout(s: str) -> str:
    return s.upper() + "!"


def words(s: str) -> int:
    counts: dict[str, int] = {}
    for w in s.split():
        counts[w] = counts.get(w, 0) + 1
    return len(counts)


def hello(name: str) -> None:
    print("hello from Pystachy,", name)


def ncalls() -> int:
    return calls


def bye(code: int) -> None:
    sys.exit(code)


def _helper(xs: list[int]) -> int:
    return sum(xs)


print("fastmath ready")
