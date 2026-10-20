# error: 'functools._lru_cache_wrapper' object has no method 'cache_parameters'
from functools import cache


@cache
def inc(x: int) -> int:
    return x + 1


print(inc.cache_parameters())
