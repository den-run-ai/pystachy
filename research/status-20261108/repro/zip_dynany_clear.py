# pystachy: dynamic-any
from typing import Any

XS: list[float] = [1.0, 2.0, 3.0, 4.0]


class It:
    def __init__(self) -> None:
        self.n = 0

    def __iter__(self) -> "It":
        return self

    def __next__(self) -> int:
        if self.n >= 4:
            raise StopIteration
        XS.clear()
        self.n += 1
        return self.n


def f(a: Any) -> float:
    t = 0.0
    for x, y in zip(XS, a):
        t += x
    return t


print(f(It()))
