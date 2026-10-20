# error: expected str | None, got int
from collections.abc import Generator


def echo() -> Generator[str, str, None]:
    while True:
        s = yield "?"
        print(s)


g = echo()
next(g)
g.send(5)
