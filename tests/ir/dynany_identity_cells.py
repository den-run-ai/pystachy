# pystachy: dynamic-any
# Closure cells retain their 16-byte scanned allocation class. Pure scalar readers
# do not box per iteration; observable copies and callback operands still snapshot.
from typing import Any


def integer(count: int) -> int:
    n = 1000

    def run(limit: int) -> int:
        nonlocal n
        for i in range(limit):
            n += 1
            n = n + 1
        return n + 0

    return run(count)


def floating(count: int) -> float:
    n = 1.5

    def run(limit: int) -> float:
        nonlocal n
        for i in range(limit):
            n += 1.0
            n = n + 1.0
        return n + 0.0

    return run(count)


def observed(count: int) -> Any:
    n = 1000

    def run(limit: int) -> Any:
        nonlocal n
        result: Any = None
        for i in range(limit):
            n += 1
            result = n
        return result

    return run(count)


def callback() -> int:
    n = 1000

    def replace() -> int:
        nonlocal n
        n = 2000
        return n + 1

    def run() -> int:
        return n + replace()

    return run()


def comprehension(count: int) -> list[int]:
    return [i + 1000 for i in range(count)]
