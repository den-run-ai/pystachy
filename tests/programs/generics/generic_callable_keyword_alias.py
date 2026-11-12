from typing import Callable


class Box[T]:
    def __init__(self, value: T) -> None:
        self.value = value


def make(x: int) -> Box[int]:
    return Box(x)


first: Callable[[int], Box[int]] = make


def inferred(fn: Callable[[int], Box], x):
    return fn(x)


print(inferred(make, 1).value)

# Inferring the generic result can publish another adapter with the same source
# function and concrete signature. Both old and new code addresses remain live.
second: Callable[[int], Box[int]] = make
print(first(x=3).value, second(x=4).value)


def invoke(fn: Callable[[int], Box[int]], x: int) -> int:
    return fn(x=x).value


print(invoke(first, 5), invoke(second, 6))
