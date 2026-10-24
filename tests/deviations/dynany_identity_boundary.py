# Documented deviation (docs/dynamic-any.md): typed numeric container items still lose
# object identity when read into Any. Calls, defaults, returns and instance fields have
# differential coverage. CPython prints True for both observations below.
# pystachy: dynamic-any
from typing import Any


xs: list[int] = [int("1000")]
a: Any = xs[0]
b: Any = xs[0]
print("a typed list's item", a is b, id(a) == id(b))
