# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


source: Any = float("nan")
optional: list[float | None] = [source]
a: Any = optional[0]
b: Any = optional[0]
print("an optional list's item", a is source, a is b)
