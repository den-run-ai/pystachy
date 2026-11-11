from typing import Callable


def memoize(f: Callable[[int], int]) -> Callable[[int], int]:
    cache: dict[int, int] = {}

    def wrapper(n: int) -> int:
        if n not in cache:
            cache[n] = f(n=n)
        return cache[n]

    return wrapper


@memoize
def fib(n: int) -> int:
    return n if n < 2 else fib(n=n - 1) + fib(n=n - 2)


print(fib(n=30), fib(n=15))


def invoke(f: Callable[[int], int], value: int) -> int:
    return f(n=value)


print(invoke(fib, 31))


def offset(base: int) -> Callable[[int], int]:
    def add(n: int) -> int:
        return base + n
    return add


print(invoke(offset(100), 5))
