# pystachy: dynamic-any
from typing import Any, Generator


def source(value: float) -> Generator[float, str | None, None]:
    try:
        command = yield value
        print("sent", command)
        yield value
    except ValueError:
        yield value
    finally:
        print("closed")


def typed(value: float) -> Generator[float, str | None, None]:
    yield from source(value)


def dynamic(value: float) -> Generator[Any, str | None, None]:
    yield from typed(value)


def check() -> None:
    original: Any = float("nan")
    g = dynamic(original)
    print("next", next(g) is original)
    print("send", g.send("again") is original)
    print("throw", g.throw(ValueError("retry")) is original)
    g.close()
    h = typed(original)
    print("typed next", next(h) is original)
    print("typed throw", h.throw(ValueError("retry")) is original)
    h.close()


check()
