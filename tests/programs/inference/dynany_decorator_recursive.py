# pystachy: dynamic-any
from typing import Any, Callable


class Step:
    def __init__(self, n: int) -> None:
        self.value: int = recursive(n - 1)


def wrap(f: Callable[[int], int]) -> Callable[[int], int]:
    return f


@wrap
def recursive(n: int) -> int:
    if n == 0:
        return 1
    if n % 2 == 0:
        return recursive(n - 1) + 1
    factory: Any = Step
    item: Any = factory(n)
    return item.value + 1


print(recursive(4))
