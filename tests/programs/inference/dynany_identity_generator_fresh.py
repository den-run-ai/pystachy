# pystachy: dynamic-any
from typing import Any, Iterator


def fresh() -> Iterator[float]:
    for i in range(4):
        yield float(i + 1000)


def aliases() -> Iterator[float]:
    x = float("1000")
    yield x
    yield x
    x = float("1000")
    yield x
    yield x


def overwritten() -> Iterator[float]:
    old = float("1000")
    yield old
    yield float("1000")
    yield old


def consume(g: Iterator[float]) -> tuple[()]:
    print("empty result", next(g))
    return ()


def pair(a: Any, b: Any) -> None:
    print("pair", a is b, a == b)


def check() -> None:
    g = fresh()
    a = b = next(g)
    pair(a, b)
    pair(next(g), next(g))
    h = aliases()
    x = next(h)
    y = next(h)
    z = next(h)
    w = next(h)
    h.close()
    pair(x, y)
    pair(y, z)
    pair(z, w)
    values: list[Any] = []
    for value in aliases():
        values.append(value)
    pair(values[0], values[1])
    pair(values[1], values[2])
    q = fresh()
    first, second, third, fourth = q
    pair(first, first)
    pair(first, second)
    print("values", third, fourth)
    last = overwritten()
    old = next(last)
    fresh_value = next(last)
    restored = next(last)
    last.close()
    pair(old, fresh_value)
    pair(old, restored)
    print("consumer", consume(fresh()))


check()
