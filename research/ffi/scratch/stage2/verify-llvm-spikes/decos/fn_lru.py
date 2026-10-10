from functools import lru_cache
@lru_cache(maxsize=None)
def f(x: int) -> int:
    return x
print(f(1))
