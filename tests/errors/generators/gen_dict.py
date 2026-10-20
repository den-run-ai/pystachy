# error: dict() of a generator is not supported: make the dict with a comprehension ({k: v for k, v in g})
from collections.abc import Iterator


def g() -> Iterator[tuple[str, int]]:
    yield "a", 1


print(dict(g()))
