from typing import Callable


def first(x: int, y: int = 10, *, scale: int = 1) -> int:
    return (x + y) * scale


def second(y: int, x: int = 20, *, scale: int = 1) -> int:
    return (x - y) * scale


def run(fn: Callable[[int, int], int]) -> int:
    return fn(y=2, x=7, scale=3)


print(run(first), run(second))


def factory(base: int) -> Callable[[int, int], int]:
    def inner(x: int, y: int = 4, *, scale: int = 1) -> int:
        return (base + x + y) * scale
    return inner


print(run(factory(30)))


class Box:
    def calc(self, x: int, y: int = 5, *, scale: int = 1) -> int:
        return x * y * scale


print(run(Box().calc))


def default(fn: Callable[[int, int], int]) -> int:
    return fn(x=7)


print(default(first), default(factory(30)), default(Box().calc))
try:
    print(default(second))
except TypeError as error:
    print(str(error))


# A later target with this Callable type must be included independently of the
# order in which the keyword caller and the conversion were compiled.
def late(x: int, y: int = 2, *, scale: int = 1) -> int:
    return (x + y + 100) * scale


print(run(late))


def expand(fn: Callable[[int, int], int]) -> int:
    return fn(*(3,), **{"y": 4})


print(expand(first))
