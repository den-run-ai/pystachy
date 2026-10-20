# error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not tuple[float] (specializing functools._lru_cache_wrapper(<function half
from functools import lru_cache


@lru_cache(maxsize=4)
def half(x: float) -> float:
    return x / 2


print(half(1.0))
