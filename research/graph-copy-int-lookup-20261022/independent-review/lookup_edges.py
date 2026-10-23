# pystachy: dynamic-any
from typing import Any

saved: list[Any] = []
g = int('1000')

class Collision:
    def __hash__(self) -> int:
        return 1000

    def __eq__(self, other: Any) -> bool:
        saved.append(other)
        return True


def typed_values(d: dict[Any, int], key: int) -> int:
    if key in d:
        return d[key]
    return -1


def receiver(d: dict[Any, int]) -> dict[Any, int]:
    global g
    g = int('1000')
    return d


def snapshot() -> None:
    global g
    g = int('1000')
    old: Any = g
    d: dict[Any, int] = {Collision(): 7}
    print(g in receiver(d))
    print(saved[-1] is old, saved[-1] is g)
    print(typed_values(d, g))
    print(saved[-1] is g)


def modes() -> None:
    d: dict[Any, int] = {1: 7, 1000: 8}
    print(typed_values(d, 1), typed_values(d, 1000), typed_values(d, 999))
    d[True] = 9
    d[1000.0] = 10
    print(typed_values(d, 1), typed_values(d, 1000))
    d[Collision()] = 11
    print(typed_values(d, 1000))

snapshot()
modes()
