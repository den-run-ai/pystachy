# error: pair() got an unexpected keyword argument 'c'
from functools import cache


@cache
def pair(a: int, b: int = 2) -> int:
    return a + b


print(pair(1, c=2))
