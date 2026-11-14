# pystachy: dynamic-any
from typing import Any

vals: list[Any] = [1, 2.5, "s", True]
for v in vals:
    print(type(v) is int, type(v) is bool)
