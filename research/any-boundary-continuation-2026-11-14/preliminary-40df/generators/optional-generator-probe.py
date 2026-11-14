# pystachy: dynamic-any
from typing import Any, Iterator


def floats(value: float | None) -> Iterator[float | None]:
    yield value
    yield None
    yield value


def ints(value: int | None) -> Iterator[int | None]:
    yield value
    yield None
    yield value


def forward(value: float | None) -> Iterator[Any]:
    yield from floats(value)


original: Any = float("nan")
g = floats(original)
a: Any = next(g)
b: Any = next(g)
c: Any = next(g)
print("float", a is original, b is None, c is original, a is c)
original_int: Any = int("1000")
h = ints(original_int)
print("int", next(h) is original_int, next(h) is None, next(h) is original_int)
f = forward(original)
print("forward", next(f) is original, next(f) is None, next(f) is original)
