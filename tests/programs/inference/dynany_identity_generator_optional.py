# pystachy: dynamic-any
from typing import Any, Iterator


def floats(value: float | None) -> Iterator[float | None]:
    yield value
    yield None
    yield value


def integers(value: int | None) -> Iterator[int | None]:
    yield value
    yield None
    yield value


def forward(value: float | None) -> Iterator[float | None]:
    yield from floats(value)


def dynamic(value: float | None) -> Iterator[Any]:
    yield from forward(value)


def objects(value: Any) -> Iterator[Any]:
    yield value
    yield None
    yield value


def narrowed(value: Any) -> Iterator[float | None]:
    yield from objects(value)


def same(a: Any, b: Any) -> bool:
    return a is b


def check() -> None:
    original: Any = float("nan")
    g = floats(original)
    first = next(g)
    middle = next(g)
    last = next(g)
    g.close()
    print("next", same(first, original), middle is None, same(last, original), same(first, last))
    default = float("nan")
    print("default", same(next(floats(original), default), original), same(next(g, default), default))
    print("none default", next(g, None) is None, next(floats(None), default) is None)
    a, b, c = forward(original)
    print("unpack", same(a, original), b is None, same(c, original))
    values = list(forward(original))
    print("list", same(values[0], original), values[1] is None, same(values[-1], original))
    expression = list(x for x in floats(original))
    print("expression", same(expression[0], original), expression[1] is None, same(expression[-1], original))
    for value in dynamic(original):
        print("dynamic", same(value, original), value is None)
    for value in narrowed(original):
        print("narrowed", same(value, original), value is None)
    boxed: Any = floats(original)
    print("boxed", next(boxed) is original, next(boxed) is None, next(boxed) is original)
    number: Any = int("1000")
    h = integers(number)
    print("int", same(next(h), number), next(h) is None, same(next(h), number))


check()
