# error: a call of square(), which lru_cache() wraps, passes its argument by keyword (n=), which CPython caches apart from a call that passes it by position, and Pystachy's key for one int or str parameter is the argument alone: pass it by position
from functools import lru_cache


@lru_cache(maxsize=4)
def square(n: int) -> int:
    return n * n


print(square(2), square(n=2))
