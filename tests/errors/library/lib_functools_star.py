# error: total() takes *args or **kwargs, which Callable[[...], R] does not match
from functools import cache


@cache
def total(*xs: int) -> int:
    return sum(xs)


print(total(1, 2))
