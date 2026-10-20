# error: the value of generator.close() is not supported (it is what a generator returns as it closes): call close() as a statement
from collections.abc import Iterator


def nums() -> Iterator[int]:
    yield 1


g = nums()
print(g.close())
