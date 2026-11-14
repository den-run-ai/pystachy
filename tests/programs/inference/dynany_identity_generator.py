# pystachy: dynamic-any
from typing import Any, Iterator


def repeat(value: float) -> Iterator[float]:
    yield value
    yield value


def forward(value: float) -> Iterator[float]:
    yield from repeat(value)


def dynamic(value: float) -> Iterator[Any]:
    yield from forward(value)


def objects() -> Iterator[float]:
    value = float("nan")
    yield value
    yield value
    value = float("nan")
    yield value


def integer(value: int) -> Iterator[int]:
    yield value
    yield value


def check() -> None:
    original: Any = float("nan")
    g = repeat(original)
    first: Any = next(g)
    second: Any = next(g)
    print("next", first is original, second is original, first is second)
    default = float("nan")
    chosen: Any = next(repeat(original), default)
    fallback: Any = next(g, default)
    print("default", chosen is original, fallback is default)
    a, b = forward(original)
    print("unpack", a is original, b is original)
    values = list(forward(original))
    print("list", values[0] is original, values[1] is original)
    values2 = list(x for x in repeat(original))
    print("expression", values2[0] is original, values2[1] is original)
    for x in dynamic(original):
        print("dynamic", x is original)
    boxed: Any = repeat(original)
    print("boxed", next(boxed) is original, next(boxed) is original)
    h = objects()
    first = next(h)
    second = next(h)
    third: Any = next(h)
    print("rebind", first is second, first is third)
    source: Any = int("1000")
    ints = integer(source)
    print("int", next(ints) is source, next(ints) is source)


check()
