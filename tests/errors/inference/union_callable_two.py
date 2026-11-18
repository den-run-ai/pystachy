# error: a closed union holds one Callable type: callable() cannot tell two apart
from typing import Callable


def pick(v: Callable[[], int] | Callable[[int], int] | int) -> int:
    return 1


print(pick(1))
