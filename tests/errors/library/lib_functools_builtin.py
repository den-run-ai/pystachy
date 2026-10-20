# error: _lru_cache_wrapper() cannot bind its type variables from the argument for 'user_function', a <built-in function len>: a <built-in function len> is no def, lambda or Callable
from functools import lru_cache

size = lru_cache(maxsize=2)(len)
print(size("abc"))
