from typing import Iterator


def values() -> Iterator[float | None]:
    value = float("nan")
    yield value
    yield None
    yield value


def integers() -> Iterator[int | None]:
    value = int("1000")
    yield value
    yield None
    yield value
