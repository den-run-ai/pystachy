from typing import Callable


def memoize(f: Callable[[int], int]) -> Callable[[int], int]:
    cache: dict[int, int] = {}

    def wrapper(n: int) -> int:
        if n not in cache:
            cache[n] = f(n)
        return cache[n]

    return wrapper


@memoize
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


print("closure", fib(80), fib(40))


class Memo:
    def __init__(self, f: Callable[[int], int]) -> None:
        self.f = f
        self.cache: dict[int, int] = {}
        self.misses = 0

    def __call__(self, n: int) -> int:
        if n not in self.cache:
            self.misses += 1
            self.cache[n] = self.f(n)
        return self.cache[n]


@Memo
def class_fib(n: int) -> int:
    return n if n < 2 else class_fib(n - 1) + class_fib(n - 2)


print("class", class_fib(80), class_fib(40), class_fib.misses)


@memoize
def plain(n: int) -> int:
    return n * 3


print("nonrecursive", plain(4), plain(4))
