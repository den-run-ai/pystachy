# pystachy: dynamic-any
"""Streaming reward scoring: typed reduction versus a dynamic observer."""
import sys
import time
from typing import Any, Iterator


def scores(count: int) -> Iterator[float]:
    for i in range(count):
        yield 1.0 / (1.0 + float((i * 73) % 97 - 48) ** 2 * 0.001)


def aliases(count: int, score: float) -> Iterator[float]:
    for _ in range(count):
        yield score


def typed(count: int, repeated: bool) -> float:
    stream = aliases(count, float("0.25")) if repeated else scores(count)
    total = 0.0
    squares = 0.0
    accepted = 0
    for score in stream:
        total += score
        squares += score * score
        if score >= 0.5:
            accepted += 1
    return total + squares + float(accepted)


def observed(count: int, repeated: bool) -> float:
    stream: Any = aliases(count, float("0.25")) if repeated else scores(count)
    total = 0.0
    squares = 0.0
    accepted = 0
    for item in stream:
        score: float = item
        total += score
        squares += score * score
        if score >= 0.5:
            accepted += 1
    return total + squares + float(accepted)


mode = sys.argv[1]
count = int(sys.argv[2])
for _ in range(int(sys.argv[3])):
    start = time.perf_counter()
    answer = observed(count, mode == "observed-alias") if mode.startswith("observed") else typed(count, mode == "typed-alias")
    print(answer, time.perf_counter() - start)
