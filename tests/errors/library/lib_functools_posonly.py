# error: positional() got some positional-only arguments passed as keyword arguments: 'a'
from functools import cache


@cache
def positional(a: int = 2, /) -> int:
    return a


print(positional(a=2))
