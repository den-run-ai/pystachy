# error: cached calls with keyword-only arguments are not supported
from functools import cache


@cache
def keyword(a: int, *, b: int = 2) -> int:
    return a + b


print(keyword(1, b=2))
