# pystachy: dynamic-any
from typing import Any, Generator


def source(value: float | None) -> Generator[float | None, str | None, None]:
    try:
        command = yield value
        print("sent", command)
        yield None
    except ValueError:
        yield value
    finally:
        print("closed")


def typed(value: float | None) -> Generator[float | None, str | None, None]:
    yield from source(value)


def dynamic(value: float | None) -> Generator[Any, str | None, None]:
    yield from typed(value)


def same(first: Any, last: Any) -> bool:
    return first is last


def check() -> None:
    original: Any = float("nan")
    g = dynamic(original)
    print("next", next(g) is original)
    print("send", g.send("again") is None)
    print("throw", g.throw(ValueError("retry")) is original)
    g.close()
    h = typed(original)
    first = next(h)
    print("typed send", h.send(None) is None)
    last = h.throw(ValueError("retry"))
    h.close()
    print("typed retained", first is original, last is original, same(first, last))
    none = typed(None)
    print("none", next(none) is None, none.throw(ValueError("retry")) is None)
    none.close()


check()
