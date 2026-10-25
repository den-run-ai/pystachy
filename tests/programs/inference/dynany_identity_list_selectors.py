# pystachy: dynamic-any
from typing import Any, Callable


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b)


first = int("1000")
second = int("1000")
large = int("2000")
xs: list[int] = [first, second, large]
a, b, c = xs
same("unpack first", a, first)
same("unpack second", b, second)
same("unpack last", c, large)
a, *rest, c = xs
same("star first", a, first)
same("star rest", rest[0], second)
same("star last", c, large)
xs[1], xs[0], xs[2] = xs
same("target first", xs[0], second)
same("target second", xs[1], first)
same("min key", min(xs, key=lambda value: value), second)
same("max key", max(xs, key=lambda value: -value), second)
same("generator min", min(value for value in xs), second)
same("generator max", max(value for value in xs), large)
same("arguments min", min(xs[0], xs[1]), second)
same("arguments max", max(xs[0], xs[2]), large)
same("arguments key", max(xs[0], xs[1], key=lambda value: -value), second)
key: Callable[[int], int] | None = (lambda value: value) if len(xs) > 2 else None
same("optional key", min(xs, key=key), second)
key = (lambda value: value) if len(xs) == 2 else None
same("none key", min(xs, key=key), second)
raw = list(range(1000, 1003))
rawcopy = raw.copy()
rawrepeat = raw * 2
same("native copy", rawcopy[0], raw[0])
same("native repeat", rawrepeat[0], rawrepeat[3])
same("native original", rawrepeat[0], raw[0])
