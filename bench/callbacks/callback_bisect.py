"""Record lookup from PR #389, with two closures sharing code but holding different offsets."""
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
callbacks: list[Callable[[Record], int]] = [
    text_length, alias_length, offset_length(5), offset_length(17),
]


def search(key) -> int:
    total = 0
    for query in queries:
        total += bisect_left(records, query, key=key)
    return total


def call_search(key: Callable[[Record], int]) -> int:
    return search(key)


def check() -> None:
    global queries
    saved = queries
    offsets = [0, 11, 5, 17]
    positions = 0
    for index in [0, 1, 2, 3, 0]:
        for query in saved:
            queries = [query]
            actual = call_search(callbacks[index])
            if actual != min(max(query - offsets[index], 0), len(records)):
                raise RuntimeError("incorrect bisect position")
            positions += 1
    queries = saved
    print("positions", positions)


def selected_index(mode: str, i: int, count: int) -> int:
    if mode == "hit":
        return 0
    if mode == "skew":
        return 1 + i % 3 if i % 10 == 9 else 0
    if mode == "mixed":
        return i % 4
    if mode == "miss":
        return 1 + i % 3
    if mode == "change":
        if count // 3 <= i < 2 * count // 3:
            return 1 + i % 3
        return 0
    raise ValueError(mode)


mode = sys.argv[1]
if mode == "check":
    check()
else:
    count = int(sys.argv[2])
    checksum = 0
    start = time.perf_counter()
    for i in range(count):
        checksum += call_search(callbacks[selected_index(mode, i, count)])
    elapsed = time.perf_counter() - start
    print(checksum)
    print(elapsed)
    if len(sys.argv) > 3 and sys.argv[3] == "memory":
        with open("/proc/self/status") as status:
            for line in status.readlines():
                if line.startswith("VmHWM:"):
                    print(line.split()[1])
