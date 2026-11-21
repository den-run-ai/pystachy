# error: expected float, got float | int (making a Callable[[], float] of <function one>
# A function annotated -> float that returns an int returns an int | float (#1534), which a
# Callable[[], float] does not hold: a Callable has one signature
from typing import Callable


def one() -> float:
    return 1


def apply(f: Callable[[], float]) -> float:
    return f() + 0.5


print(apply(one))
