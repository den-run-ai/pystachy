# error: 'Callable[[], int] | int' object is not callable
from typing import Callable


def value(v: Callable[[], int] | int) -> int:
    return v()


print(value(lambda: 1))
