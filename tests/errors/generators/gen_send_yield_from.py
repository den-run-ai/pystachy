# error: outer() takes str from send(), which yield from sends on to a generator that takes None: annotate them with the same send type
from collections.abc import Generator, Iterator


def inner() -> Iterator[int]:
    x = yield 1
    print(x)


def outer() -> Generator[int, str, None]:
    yield from inner()


g = outer()
next(g)
g.send("a")
