# A plain generator in loops (#988): neither body can recur, so its resumes and the loops' drops
# need no recursion accounting. Usage: generator_loops.py ITERATIONS; prints a checksum.
import sys
from collections.abc import Iterator


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield (i * i) & 1023


def pairs(items: list[int]) -> Iterator[tuple[int, int]]:
    for i in range(1, len(items)):
        yield items[i - 1], items[i]


def total(n: int) -> int:
    t = 0
    for v in squares(n):
        t += v
    items = [i & 255 for i in range(1000)]
    for _ in range(n // 1000):
        for a, b in pairs(items):
            t += a ^ b
    return t


print(total(int(sys.argv[1])))
