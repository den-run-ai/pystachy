# pystachy: dynamic-any
"""Streaming iteration through Any, with checksums and deterministic work counts.

  python3.13 tools/dynany_iteration_bench.py list 100000
  ./pystachy run tools/dynany_iteration_bench.py object 100000 smoke

Kinds: list, range, object, generator. All consume exactly N integers; the object
and generator also verify that production stays one item ahead of consumption.
Normal mode prints construction and processing CPU nanoseconds separately; smoke
mode prints processing CPU seconds to stderr for the existing benchmark protocol.
This standalone driver intentionally does not add unsupported code to the older
base/head graph driver (dynany_bench.py).
"""
import sys
from time import process_time_ns
from typing import Any


class Steps:
    def __init__(self):
        self.count = 0


class CountIterator:
    def __init__(self, n: int, steps: Steps):
        self.n = n
        self.i = 0
        self.steps = steps

    def __next__(self) -> int:
        self.steps.count += 1
        if self.i == self.n:
            raise StopIteration
        value = self.i
        self.i += 1
        return value


class Count:
    def __init__(self, n: int, steps: Steps):
        self.n = n
        self.steps = steps

    def __iter__(self) -> CountIterator:
        return CountIterator(self.n, self.steps)


def generated(n: int, steps: Steps):
    for i in range(n):
        steps.count += 1
        yield i
    steps.count += 1


def source(kind: str, n: int, steps: Steps) -> Any:
    if kind == "list":
        return [i for i in range(n)]
    if kind == "range":
        return range(n)
    if kind == "object":
        return Count(n, steps)
    return generated(n, steps)


def consume(values: Any, steps: Steps, counted: bool) -> tuple[int, int]:
    total = 0
    consumed = 0
    for value in values:
        assert isinstance(value, int)
        if counted:
            # Materializing the producer before this loop violates its contract.
            assert steps.count == consumed + 1
        total += value
        consumed += 1
    return total, consumed


def iteration(kind: str, n: int, smoke: bool) -> None:
    steps = Steps()
    start = process_time_ns()
    values = source(kind, n, steps)
    built = process_time_ns()
    counted = kind == "object" or kind == "generator"
    assert steps.count == 0
    total, consumed = consume(values, steps, counted)
    end = process_time_ns()
    assert consumed == n and total == n * (n - 1) // 2
    assert steps.count == (n + 1 if counted else 0)
    print(kind, total, consumed, steps.count)
    if smoke:
        print("seconds", (end - built) / 1000000000, file=sys.stderr)
    else:
        print("nanoseconds", built - start, end - built)


kind = sys.argv[1]
n = int(sys.argv[2])
assert kind in ["list", "range", "object", "generator"]
assert n >= 0 and n <= 10000000
iteration(kind, n, len(sys.argv) > 3 and sys.argv[3] == "smoke")
