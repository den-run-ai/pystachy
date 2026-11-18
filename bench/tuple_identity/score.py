# pystachy: dynamic-any
"""Numeric tuple reward batches with optional identity observation and copies."""
import sys
import time
from typing import Any


def number(value: Any) -> float:
    return value


def score(count: int, mode: str) -> float:
    total = 0.0
    for i in range(count):
        values: tuple[float, ...] = (float(i % 97) * 0.125, float(i % 53) * 0.25)
        if mode == "copy":
            tail = values[1:]
            total += tail[0] + values[0]
        elif mode == "observed":
            total += number(values[0]) + number(values[1])
        else:
            total += values[0] + values[1]
    return total


mode = sys.argv[1]
count = int(sys.argv[2])
for _ in range(int(sys.argv[3])):
    start = time.perf_counter()
    answer = score(count, mode)
    print(answer, time.perf_counter() - start)
