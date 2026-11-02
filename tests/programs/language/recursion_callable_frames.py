# A call through a function value counts one frame, as in CPython (#988): a Callable's adapter
# only forwards to its target and adds none. Recursions through a list, a dict and a global of
# function values that CPython completes near the limit complete, and an unbounded one is caught.
import sys
from collections.abc import Callable

steps: list[Callable[[int], int]] = []
table: dict[str, Callable[[int], int]] = {}


def by_index(n: int) -> int:
    if n == 0:
        return 0
    return steps[0](n - 1) + 1


def by_key(n: int) -> int:
    if n == 0:
        return 0
    return table["key"](n - 1) + 1


def by_global(n: int) -> int:
    if n == 0:
        return 0
    return again(n - 1) + 1


steps.append(by_index)
table["key"] = by_key
again: Callable[[int], int] = by_global
original = sys.getrecursionlimit()
sys.setrecursionlimit(100)
for depth in (10, 90):
    print(depth, by_index(depth), by_key(depth), by_global(depth))
try:
    print(by_index(500))
except RecursionError:
    print("caught")
print(by_key(90))
sys.setrecursionlimit(original)
print(sys.getrecursionlimit() == original)
