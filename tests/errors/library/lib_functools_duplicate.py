# error: pair() got multiple values for argument 'a'
from functools import cache


@cache
def pair(a: int, b: int = 2) -> int:
    return a + b


print(pair(1, a=2))
