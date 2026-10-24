# pystachy: dynamic-any
from typing import Any

d: Any = {"a": 1}
d.update({"b": "two", "c": None})
print(d)
