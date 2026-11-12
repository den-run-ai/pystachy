# error: expected str, got int
from typing import Callable


def decorate(f: Callable[[int], int]) -> Callable[[int], int]:
    return f


@decorate
def wrong(n: str) -> int:
    return 0 if len(n) == 0 else wrong(n[1:])


print(wrong(3))
