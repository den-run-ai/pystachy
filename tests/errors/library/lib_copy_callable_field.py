# error: copy.deepcopy() of a value of type Callable[[int], int] is not supported: it may hold a bound method
# A Callable value may hold a bound method, whose deep copy CPython binds to a copy of its object (here a function, so CPython prints 4)
import copy
from typing import Callable


class Job:
    def __init__(self, f: Callable[[int], int]) -> None:
        self.f = f


def double(x: int) -> int:
    return 2 * x


print(copy.deepcopy(Job(double)).f(2))
