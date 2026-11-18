# pystachy: dynamic-any
from typing import Any, Iterator


def fresh() -> Iterator[float | None]:
    yield float("1000")
    yield None
    yield float("1000")


def aliases() -> Iterator[float | None]:
    value = float("nan")
    yield value
    yield None
    yield value
    value = float("nan")
    yield value
    yield value


def retained() -> Iterator[float | None]:
    value: float | None = float("nan")
    yield value
    value = None
    yield value
    value = float("nan")
    yield value


def literal() -> Iterator[float | None]:
    yield 1.25


def pair(left: Any, right: Any) -> None:
    print("pair", left is right)


def advance(g: Iterator[float | None], original: Any) -> Any:
    print("advance", next(g) is None)
    next(g)
    g.close()
    return original


def advance_alias(g: Iterator[float | None]) -> float | None:
    print("advance alias", next(g) is None)
    last = next(g)
    g.close()
    return last


def check() -> None:
    g = fresh()
    first = alias = next(g)
    print("none", next(g) is None)
    last = next(g)
    g.close()
    pair(first, alias)
    pair(first, last)
    h = aliases()
    first = next(h)
    print("between", next(h) is None)
    second = next(h)
    third = next(h)
    fourth = next(h)
    h.close()
    pair(first, second)
    pair(second, third)
    pair(third, fourth)
    values: list[Any] = []
    for value in aliases():
        values.append(value)
    pair(values[0], values[2])
    pair(values[2], values[3])
    pair(values[3], values[4])
    selected = retained()
    original: Any = next(selected)
    pair(original, advance(selected, original))
    delayed = aliases()
    pair(next(delayed), advance_alias(delayed))
    left, empty, right = fresh()
    print("unpack", left == right, empty is None)
    pair(left, right)
    constant = 1.25
    pair(next(literal()), constant)


check()
