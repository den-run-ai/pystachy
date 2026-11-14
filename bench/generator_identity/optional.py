# pystachy: dynamic-any
"""Sparse optional reward streams: typed consumption and dynamic observation."""
from typing import Any, Iterator
import sys


def fresh(count: int) -> Iterator[float | None]:
    for index in range(count):
        if index % 16 == 0:
            yield None
        else:
            yield 1.0 / (1.0 + float(index % 31))


def aliases(count: int) -> Iterator[float | None]:
    value = float("0.25")
    for index in range(count):
        if index % 16 == 0:
            yield None
        else:
            yield value


def typed(values: Iterator[float | None]) -> None:
    total = 0.0
    missing = 0
    for value in values:
        if value is None:
            missing += 1
        else:
            total += value
    print(total, missing)


def observed(values: Any) -> None:
    total = 0.0
    missing = 0
    for value in values:
        if value is None:
            missing += 1
        else:
            number: float = value
            total += number
    print(total, missing)


mode = sys.argv[1]
count = int(sys.argv[2])
if mode == "typed":
    typed(fresh(count))
elif mode == "observed":
    observed(fresh(count))
elif mode == "typed-alias":
    typed(aliases(count))
elif mode == "observed-alias":
    observed(aliases(count))
else:
    raise ValueError("unknown mode")
