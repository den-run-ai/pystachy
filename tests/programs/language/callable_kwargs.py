from typing import Callable


def double(x: int) -> int:
    return x * 2


f: Callable[[int], int] = double
print(f(x=2))
