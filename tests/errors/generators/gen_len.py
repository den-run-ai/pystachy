# error: object of type 'generator' has no len()
from collections.abc import Iterator


def g() -> Iterator[int]:
    yield 1


print(len(g()))
