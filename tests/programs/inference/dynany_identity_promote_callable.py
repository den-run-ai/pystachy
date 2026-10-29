# No opt-in here: the python-int gate promotes this entry module independently.
from typing import Callable
import intidentity


def identity(value: int) -> int:
    return value


class Reader:
    def identity(self, value: int) -> int:
        return value


def apply(fn: Callable[[int], int], value: int) -> int:
    return fn(value)


value = int("8000")
fn: Callable[[int], int] = identity
method: Callable[[int], int] = Reader().identity
intidentity.keep(value)
intidentity.keep(fn(value))
intidentity.check("indirect function")
intidentity.keep(value)
intidentity.churn()
intidentity.keep(method(value))
intidentity.check("indirect method")
intidentity.keep(value)
intidentity.keep(apply(fn, value))
intidentity.check("Callable parameter")
