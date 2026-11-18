# Documented deviation (docs/dynamic-any.md): union numeric list items lose object
# identity when read into Any; wide constant expressions are not pooled. Calls,
# defaults, returns, instance fields and numeric/optional lists have differential
# coverage. CPython prints True for every observation below.
# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


source: Any = float("nan")
joined: list[int | float] = [source]
a: Any = joined[0]
b: Any = joined[0]
print("a union list's item", a is source, a is b)

a = 2 ** 63
b = 9223372036854775808
print("a folded wide constant", a is b, id(a) == id(b))
