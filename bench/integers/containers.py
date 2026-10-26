# pystachy: python-int
# Mixed small/large values in lists, dicts and sorting.
import sys
import time


def run(n: int) -> int:
    values: list[int] = []
    for i in range(n):
        values.append((i * 2654435761) % 4294967296 if i % 3 else 2 ** 64 + i)
    values.sort()
    counts: dict[int, int] = {}
    for v in values:
        k = v % 1000
        counts[k] = counts.get(k, 0) + 1
    return sum(values) % 1000000007 + len(counts) + values[n // 2] % 1000


n = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
start = time.perf_counter()
r = run(n)
elapsed = time.perf_counter() - start
print(r)
print(elapsed)
