# pystachy: dynamic-any
from typing import Any, Iterator


def integers(value: int) -> Iterator[int]:
    yield value
    yield value


def floats(value: float) -> Iterator[float]:
    yield value
    yield value


def optional_ints(value: int) -> Iterator[int | None]:
    yield None
    yield from integers(value)


def optional_floats(value: float) -> Iterator[float | None]:
    yield None
    yield from floats(value)


integer: Any = int("1000")
number: Any = float("nan")
ints = optional_ints(integer)
print("int", next(ints) is None, next(ints) is integer, next(ints) is integer)
values = optional_floats(number)
print("float", next(values) is None, next(values) is number, next(values) is number)
