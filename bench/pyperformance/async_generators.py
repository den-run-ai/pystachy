"""
Benchmark recursive async generators implemented in python
by traversing a binary tree.

Author: Kumar Aditya
"""

from __future__ import annotations

from collections.abc import AsyncIterator

# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.
import sys
import time


class Tree:
    def __init__(self, left: Tree | None, value: int, right: Tree | None) -> None:
        self.left = left
        self.value = value
        self.right = right

    async def __aiter__(self) -> AsyncIterator[int]:
        if self.left:
            async for i in self.left:
                yield i
        yield self.value
        if self.right:
            async for i in self.right:
                yield i


def tree(input: range) -> Tree | None:
    n = len(input)
    if n == 0:
        return None
    i = n // 2
    return Tree(tree(input[:i]), input[i], tree(input[i + 1:]))

# Pystachy port: a size argument bounds smoke/GC runs; normal size stays 100000.
async def bench_async_generators(size: int = 100000) -> None:
    async for _ in tree(range(size)):
        pass


# Pystachy port: pyperf's bench_async_func() awaits the benchmark in an asyncio event loop.
# Nothing in it suspends, so send(None) runs a coroutine to its end, as in coroutines.py.
def run(coro) -> None:
    try:
        while True:
            coro.send(None)
    except StopIteration:
        pass


# Pystachy port: the values the traversal yields, collected outside the timed region to check them.
VALUES: list[int] = []


async def collect(size: int) -> None:
    async for value in tree(range(size)):
        VALUES.append(value)

if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the number of runs
    # and argv[2] the tree's size; outside the timer, every value that the traversal yields is
    # checked, and their count and sum are printed.
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    t0 = time.perf_counter()
    for _ in range(loops):
        run(bench_async_generators(size))
    print("seconds", time.perf_counter() - t0, file=sys.stderr)
    run(collect(size))
    assert VALUES == list(range(size))
    print("async_generators", loops, size, len(VALUES), sum(VALUES))
