# error: double()'s parameter 'x' has no annotation, which the type variables it matches take their type from
from functools import lru_cache


@lru_cache(maxsize=4)
def double(x) -> int:
    return x * 2


print(double(1))
