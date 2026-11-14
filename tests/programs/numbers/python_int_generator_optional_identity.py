# pystachy: dynamic-any
# pystachy: python-int
from typing import Any, Iterator


def optional(value: int | None) -> Iterator[int | None]:
    yield value
    yield None
    yield value


def raw(value: int) -> Iterator[int]:
    yield value
    yield value


def forwarded(value: int) -> Iterator[int | None]:
    yield None
    yield from raw(value)


def check(value: Any) -> None:
    g = optional(value)
    first = next(g)
    print("optional", first is value, next(g) is None, next(g) is value)
    h = forwarded(value)
    print("forwarded", next(h) is None, next(h) is value, next(h) is value)
    print("default", next(g, value) is value, next(g, None) is None)
    boxed: Any = optional(value)
    print("boxed", next(boxed) is value, next(boxed) is None, next(boxed) is value)


check(int("1000"))
check(int("9223372036854775807"))
check(int("-9223372036854775808"))
