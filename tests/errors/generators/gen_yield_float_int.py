# error: expected float, got int (write a float literal like 1.0, or use float())
from collections.abc import Iterator


def halves() -> Iterator[float]:
    yield 1
    yield 1.5


print(list(halves()))
