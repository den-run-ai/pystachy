"""
Benchmark recursive generators implemented in python
by traversing a binary tree.

Author: Kumar Aditya
"""

from __future__ import annotations

from collections.abc import Iterator

# Pystachy port: keep upstream timers, collecting seconds for the deterministic runner.
import time
import sys

TIMED: list[float] = []


class Tree:
    def __init__(self, left: Tree | None, value: int, right: Tree | None) -> None:
        self.left = left
        self.value = value
        self.right = right

    def __iter__(self) -> Iterator[int]:
        if self.left:
            yield from self.left
        yield self.value
        if self.right:
            yield from self.right


def tree(input: range) -> Tree | None:
    n = len(input)
    if n == 0:
        return None
    i = n // 2
    return Tree(tree(input[:i]), input[i], tree(input[i + 1:]))

# Pystachy port: a size argument bounds smoke/GC runs; normal size stays 100000.
def bench_generators(loops: int, size: int = 100000) -> int:
    assert list(tree(range(10))) == list(range(10))
    range_it = range(loops)
    iterable = tree(range(size))  # Pystachy port: configurable smoke size
    t0 = time.perf_counter()
    for _ in range_it:
        for _ in iterable:
            pass
    # Pystachy port: check every yielded value outside the upstream timed region.
    TIMED.append(time.perf_counter() - t0)
    values = list(iterable) if iterable is not None else []
    assert values == list(range(size))
    return sum(values)

# Pystachy port: a deterministic main replaces pyperf.Runner.
if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    result = bench_generators(loops, size)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("generators", loops, size, result)
