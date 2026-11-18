# pystachy: dynamic-any
# pystachy: python-int
# Existing checked 64-bit storage boundary (docs/python-int.md#64-bit-boundaries):
# an optional numeric generator channel holds a nullable 64-bit representation.
# Identity companions do not widen that payload. CPython yields these wide ints.
from typing import Iterator


def direct(value: int) -> Iterator[int | None]:
    print("direct entered")
    yield value


def optional(value: int | None) -> Iterator[int | None]:
    print("optional entered")
    yield value


def forwarded(value: int | None) -> Iterator[int | None]:
    yield from optional(value)


for value in [2 ** 63, -2 ** 63 - 1]:
    first = direct(value)
    try:
        print(next(first))
    except OverflowError:
        print("direct overflow")
    print("direct done", next(first, None) is None)
    second = optional(value)
    try:
        print(next(second))
    except OverflowError:
        print("optional overflow")
    print("optional done", next(second, None) is None)
    last = forwarded(value)
    try:
        print(next(last))
    except OverflowError:
        print("forwarded overflow")
    print("forwarded done", next(last, None) is None)
