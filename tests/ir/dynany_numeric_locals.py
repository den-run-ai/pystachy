# pystachy: dynamic-any
# Closed numeric functions need no identity boxes; an observable copy still does.
# Immutable numeric parameters reuse incoming boxes; local aliases remain lazy.
from typing import Any


def integer(n: int, seed: int) -> int:
    x = seed
    total = 0
    for i in range(n):
        x = (x * 17 + 3) % 1000003
        y = x
        total += y
    return total


def floating(n: int, seed: int) -> int:
    x = float(seed)
    total = 0
    for i in range(n):
        x = (x * 1.25 + 3.0) % 1000.0
        y = x
        total += int(y)
    return total


def conditional(x: float, positive: bool) -> float:
    y = x if positive else -x
    z = y
    return z


def same(x: Any, y: Any) -> bool:
    return x is y


def observable(x: float) -> bool:
    y = x
    return same(x, y)


def dynamic_local(x: float) -> bool:
    y = x
    value: Any = y
    return value is x


def dynamic_return(x: float) -> Any:
    y = x
    return y
