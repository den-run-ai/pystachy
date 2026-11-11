# pystachy: dynamic-any
from typing import Any, Callable

values: list[int] = [int("1000"), int("2000")]
expected: Any = values[1]
result: Any = max(iter(values), default=None)
print(result is expected)
fallback = int("3000")
original: Any = fallback
empty: list[int] = []
result = min(iter(empty), default=fallback)
print(result is original)


def keep(value: int) -> int:
    return value


def choose(fn: Callable[[int], int] | None) -> int | None:
    return max(iter(values), key=fn, default=None)


print(choose(None) is expected, choose(keep) is expected)
