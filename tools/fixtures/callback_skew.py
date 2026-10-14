"""Runtime callback identity through the unchanged standard-library bisect loop.

The erased Callable comes from a mutable list. Both named callbacks have the
same signature; their identity, rather than their argument types, is dynamic.
The main workload indexes text records by field length. No concrete search
control is present here; the runner derives one by changing dispatch only.
"""
import sys
import time
from bisect import bisect_left
from typing import Callable


class Record:
    def __init__(self, text: str, alias: str) -> None:
        self.text = text
        self.alias = alias


def text_length(record: Record) -> int:
    return len(record.text)


def alias_length(record: Record) -> int:
    return len(record.alias)


def offset_length(offset: int) -> Callable[[Record], int]:
    def key(record: Record) -> int:
        return len(record.text) + offset
    return key


records: list[Record] = []
queries: list[int] = []
for i in range(1024):
    records.append(Record("a" * i, "b" * (i + 11)))
for i in range(509):
    queries.append((i * 569) % 1025)
callbacks: list[Callable[[Record], int]] = [text_length, alias_length, offset_length(5)]


def search(key) -> int:
    total = 0
    for query in queries:
        total += bisect_left(records, query, key=key)
    return total


def call_search(key: Callable[[Record], int]) -> int:
    return search(key)


def dispatch(index: int) -> int:
    return call_search(callbacks[index])


def expected_position(query: int, index: int) -> int:
    offset = 0 if index == 0 else 11 if index == 1 else 5
    return min(max(query - offset, 0), len(records))


def check() -> None:
    # A one-query batch makes the ordinary search return that exact position.
    # Calls after the threshold validate the loaded body, both fallback targets,
    # and recovery, with every query independently checked (not just a checksum).
    global queries
    saved = queries
    count = 0
    checksum = 0
    for index in [0, 1, 2, 0]:
        for query in saved:
            queries = [query]
            actual = dispatch(index)
            expected = expected_position(query, index)
            if actual != expected:
                raise RuntimeError("incorrect bisect position")
            count += 1
            checksum += actual
    queries = saved
    print("positions", count, checksum)


def selected_index(phase: str, i: int, count: int) -> int:
    if phase == "cold":
        return 1 if i == count - 1 else 0
    if phase == "shift":
        half = count // 2
        if i < half:
            return i % 3
        return 0 if i == count - 1 else 1 + i % 2
    return 0


def phase_batch(name: str, count: int) -> None:
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    checksum = 0
    for i in range(count):
        checksum += dispatch(selected_index(name, i, count))
    elapsed_cpu = time.process_time() - start_cpu
    elapsed_wall = time.perf_counter() - start_wall
    print("phase", name, count, checksum, elapsed_wall, elapsed_cpu)


mode = sys.argv[1] if len(sys.argv) > 1 else "check"
if mode == "check":
    check()
else:
    cold = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    warm = int(sys.argv[3]) if len(sys.argv) > 3 else 50000
    shift = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    recovery = int(sys.argv[5]) if len(sys.argv) > 5 else 50000
    phase_batch("cold", cold)
    phase_batch("warm", warm)
    phase_batch("shift", shift)
    phase_batch("recovery", recovery)
