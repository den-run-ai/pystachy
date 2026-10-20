# error: 'generator' object is not subscriptable
from collections.abc import Iterator


def g() -> Iterator[int]:
    yield 1


print(g()[0])
