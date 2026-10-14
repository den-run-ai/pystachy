"""Statically typed counterpart of examples/native_dynamic.py's hot region.

The benchmark uses the same helper, sumsq body, input and number of calls in
baseline, adaptive and static modes. It reports in-process warm execution time;
the runner records cold build/compilation time separately.
"""
import sys
import time


def helper(x: int) -> int:
    return x * x


def sumsq(n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + helper(i)
        i = i + 1
    return total


def batch(n: int, count: int) -> int:
    total = 0
    i = 0
    while i < count:
        total = total + sumsq(n + i % 7)
        i = i + 1
    return total


def main() -> None:
    n = int(sys.argv[1])
    repeats = int(sys.argv[2])
    warmups = int(sys.argv[3])
    result = 0
    for i in range(warmups):
        result = batch(n, repeats)
    start = time.perf_counter()
    result = batch(n, repeats)
    elapsed = time.perf_counter() - start
    print("RESULT\tbatch\tint\t" + str(result) + "\t" + str(elapsed))


if __name__ == "__main__":
    main()
