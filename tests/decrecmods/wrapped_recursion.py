from typing import Callable


def wrap(f: Callable[[int], int]) -> Callable[[int], int]:
    def called(n: int) -> int:
        return f(n)
    return called


@wrap
def factorial(n: int) -> int:
    return 1 if n < 2 else n * factorial(n - 1)
