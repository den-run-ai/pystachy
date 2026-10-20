# error: a method call of an Any value takes positional arguments only (o.sort(...))
# pystachy: dynamic-any
from typing import Any

v: Any = [3, 1, 2]
v.sort(reverse=True)
print(v)
