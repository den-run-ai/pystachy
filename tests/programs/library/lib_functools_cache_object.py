# functools.cache and lru_cache of functions that take objects: the cache keys them as dicts do,
# by identity where the class defines neither __eq__ nor __hash__, else by those methods
from functools import cache, lru_cache


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


class Val:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Val) and self.v == other.v

    def __hash__(self) -> int:
        return self.v


calls: list[int] = []


@cache
def unbox(b: Box) -> int:
    calls.append(b.v)
    return b.v * 10


@lru_cache(maxsize=2)
def scaled(v: Val, k: int) -> int:
    calls.append(v.v)
    return v.v * k


a = Box(1)
print(unbox(a), unbox(a), unbox(Box(1)), calls, unbox.cache_info())
calls.clear()
print(scaled(Val(1), 2), scaled(Val(1), 2), scaled(Val(2), 2), scaled(Val(3), 2), scaled(Val(1), 2), calls)
print(scaled.cache_info())
unbox.cache_clear()
print(unbox(a), unbox.cache_info())
