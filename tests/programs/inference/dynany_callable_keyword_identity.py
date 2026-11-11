# pystachy: dynamic-any
from typing import Any, Callable


def same(left: Any, right: Any) -> bool:
    return left is right


def keep(x: int, y: int = 0) -> int:
    return x


def choose(fn: Callable[[int, int], int], value: int) -> bool:
    return same(fn(y=10, x=value), value)


value = int("1000000")
print(choose(keep, value))


def closure(value: int) -> Callable[[int, int], int]:
    def inner(x: int, y: int = value) -> int:
        return y
    return inner


fn = closure(value)
print(same(fn(x=1), value))

shared: list[int] = [value]


def read(x: list[int]) -> list[int]:
    return x


def forward(fn: Callable[[list[int]], list[int]], values: list[int]) -> list[int]:
    return fn(x=values)


print(forward(read, shared) is shared)
