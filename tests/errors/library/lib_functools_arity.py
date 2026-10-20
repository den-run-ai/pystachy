# error: inc() takes 1 positional argument but 2 were given
from functools import cache


@cache
def inc(x: int) -> int:
    return x + 1


print(inc(1, 2))
