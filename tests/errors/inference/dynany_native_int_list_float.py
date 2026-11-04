# error: an Any value cannot be used as list[float] (narrow it with isinstance() first)
# pystachy: dynamic-any
# A native int-list box never licenses reading its raw bits as float items.
from typing import Any

items: list[int] = [1, 2]
value: Any = items
floats: list[float] = value
floats[0] = 3.5
print(items)
