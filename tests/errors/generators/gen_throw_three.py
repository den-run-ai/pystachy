# error: generator.throw() takes one argument, the exception (throw(type, value, traceback) is deprecated and not supported)
from collections.abc import Iterator


def nums() -> Iterator[int]:
    yield 1


g = nums()
next(g)
g.throw(ValueError, ValueError("x"), None)
