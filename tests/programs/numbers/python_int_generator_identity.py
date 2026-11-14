# pystachy: dynamic-any
# pystachy: python-int
from typing import Any, Iterator
from wide import repeat
from yields import repeat as floats


def forward(value: int) -> Iterator[Any]:
    yield from repeat(value)


def check(value: Any) -> None:
    g = repeat(value)
    first: Any = next(g)
    second: Any = next(g)
    print("typed", first == value, first is value, second is value)
    a, b = repeat(value)
    print("unpack", a is value, b is value)
    h = forward(value)
    print("forward", next(h) is value, next(h) is value)
    boxed: Any = repeat(value)
    print("boxed", next(boxed) is value, next(boxed) is value)


check(int("1000"))
check(int("18446744073709551617"))
original: Any = float("nan")
g = floats(original)
print("import", next(g) is original, next(g) is original)
