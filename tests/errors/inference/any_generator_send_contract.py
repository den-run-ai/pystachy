# error: expected str | None, got int
from typing import Any, Generator


def values() -> Generator[Any, str | None, None]:
    value = yield 1
    print(value)


g = values()
next(g)
g.send(5)
