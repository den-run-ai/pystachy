# error: pair() missing 1 required positional argument: 'a'
from functools import cache


@cache
def pair(a: int, b: int = 2) -> int:
    return a + b


print(pair(b=2))
