# An adapter whose static branch excludes an unbound decorated name still
# compiles eagerly: its fill supplies an empty global's concrete storage type.
from typing import Callable

values = []


def decorate(f: Callable[[int], int]) -> Callable[[int], int]:
    f(1)
    return f


@decorate
def fill(n: int) -> int:
    if isinstance(n, str):
        return later(n)
    values.append(n)
    return n


print(values)


@decorate
def later(n: int) -> int:
    return n


print(fill(2), values)
