# error: expected str, got int
from typing import Callable


def decorate(f: Callable[[int], int]) -> Callable[[int], int]:
    return f


@decorate
def wrong(n: int) -> str:
    return "done" if n == 0 else wrong(n - 1)


print(wrong(3))
