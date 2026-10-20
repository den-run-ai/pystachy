# error: yield from list[int] in outer(), which takes str from send(), is not supported: PEP 380 sends the value on to the iterator, which has no send() (iterate it with for and yield each item)
from collections.abc import Generator


def outer() -> Generator[int, str, None]:
    yield from [1, 2]


g = outer()
next(g)
print(g.send("a"))
