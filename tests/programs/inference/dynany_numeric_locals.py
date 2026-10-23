# pystachy: dynamic-any
from typing import Any


def integer(n: int, seed: int = 123) -> int:
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


def control(n: int, x: float, choose: bool) -> float:
    total = 0.0
    while n > 0:
        n -= 1
        if n == 2:
            continue
        if n < 1:
            break
        copied = x if choose else -x
        copied = copied
        total += copied
    return total


def named(n: int, seed: int) -> int:
    total = 0
    for i in range(n):
        copied = (seed := (seed * 17 + 3) % 1000003)
        total += copied
    return total


def same(x: Any, y: Any) -> bool:
    return x is y


def identity(x: float) -> bool:
    y = x
    return same(x, y)


def annotated(x: float) -> bool:
    y = x
    value: Any = y
    return value is x


def boxed(x: Any) -> Any:
    y = x
    return y


for n in [0, 1, 9, 1000]:
    print(n, integer(n), integer(n, -123), floating(n, 123), named(n, 123))
for choose in [False, True]:
    print(control(7, 1.5, choose))
for x in [0.0, -0.0, float("nan"), 3.25]:
    print(identity(x), annotated(x))
    value: Any = x
    print(boxed(value) is value)
# Dynamic argument conversion reaches the same closed numeric ABI.
count: Any = 9
seed: Any = 123
print(integer(count, seed), floating(count, seed))
