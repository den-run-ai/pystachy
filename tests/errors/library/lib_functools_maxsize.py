# error: _lru_cache_wrapper() cannot bind its type variables from the argument for 'user_function', a str: a str is no def, lambda or Callable
from functools import lru_cache


@lru_cache("big")
def scale(x: int) -> int:
    return x * 2


print(scale(2))
