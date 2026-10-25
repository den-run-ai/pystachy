# Documented deviation (docs/dynamic-any.md): typed tuple and optional/union numeric list items lose
# object identity when read into Any. Calls, defaults, returns, instance fields and numeric lists have
# differential coverage. CPython prints True for every observation below.
# pystachy: dynamic-any
from typing import Any


xs: tuple[int, ...] = (int("1000"),)
a: Any = xs[0]
b: Any = xs[0]
print("a typed tuple's item", a is b, id(a) == id(b))

source: Any = float("nan")
optional: list[float | None] = [source]
a = optional[0]
b = optional[0]
print("an optional list's item", a is source, a is b)
joined: list[int | float] = [source]
a = joined[0]
b = joined[0]
print("a union list's item", a is source, a is b)
