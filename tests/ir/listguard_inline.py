# listguard copies a range loop whose item reads and assignments it can leave unchecked (#1300). In
# the copy, a call of a function that the program calls nowhere else is marked alwaysinline: LLVM
# inlines an internal function's only call, and with two (the loop's and the copy's) would inline
# neither, as it once left float's Point.__init__ out of line. The loop's call is then the last,
# which LLVM inlines too. A function called elsewhere too, or named as a value (a Callable),
# keeps its calls as they are, and a loop whose ops and its only-called callees' are more than
# listguard copies keeps no copy.
from typing import Callable


class Point:
    def __init__(self, i: int):
        self.x: float = i * 0.5
        self.y: float = i * 2.0


def scale(x: float) -> float:
    return x * 3.0


def twice(x: float) -> float:
    return x * 2.0


def big(i: int) -> float:
    x = float(i)
    x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5
    x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5
    x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5
    x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5
    x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5; x = x * 1.01 + 0.5
    return x


def fill(n: int) -> list[Point | None]:
    points: list[Point | None] = [None] * n
    for i in range(n):
        points[i] = Point(i)
    return points


def scaled(xs: list[float]) -> list[float]:
    ys = [0.0] * len(xs)
    for i in range(len(xs)):
        ys[i] = scale(xs[i])
    return ys


def doubled(xs: list[float]) -> list[float]:
    ys = [0.0] * len(xs)
    for i in range(len(xs)):
        ys[i] = twice(xs[i])
    return ys


def bigloop(n: int) -> list[float]:
    ys = [0.0] * n
    for i in range(n):
        ys[i] = big(i)
    return ys


op: Callable[[float], float] = twice
print(len(fill(3)), scaled([1.0, 2.0]), scale(1.5), len(bigloop(2)), doubled([1.0]), op(2.0))
