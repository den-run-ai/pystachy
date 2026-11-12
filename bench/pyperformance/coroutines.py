"""
Benchmark for recursive coroutines.

Author: Kumar Aditya
"""

# Pystachy port: keep upstream timers, collecting seconds for the deterministic runner.
import time
import sys

TIMED: list[float] = []


async def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return await fibonacci(n - 1) + await fibonacci(n - 2)


# Pystachy port: the value fibonacci() returns, which await gives (StopIteration's value is not
# available): the checksum, computed outside the upstream timed region.
RESULTS: list[int] = []


async def record(n: int) -> None:
    RESULTS.append(await fibonacci(n))


# Pystachy port: an argument n bounds smoke/GC runs; the normal run keeps fibonacci(25).
def bench_coroutines(loops: int, n: int = 25) -> int:
    range_it = range(loops)
    t0 = time.perf_counter()
    for _ in range_it:
        coro = fibonacci(n)  # Pystachy port: configurable smoke size
        try:
            while True:
                coro.send(None)
        except StopIteration:
            pass
    # Pystachy port: the seconds, which upstream returns; then the checked result.
    TIMED.append(time.perf_counter() - t0)
    check = record(n)
    try:
        while True:
            check.send(None)
    except StopIteration:
        pass
    return RESULTS[-1]


# Pystachy port: a deterministic main replaces pyperf.Runner.
if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    result = bench_coroutines(loops, n)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("coroutines", loops, n, result)
