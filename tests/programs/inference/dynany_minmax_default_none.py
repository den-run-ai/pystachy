# pystachy: dynamic-any
# Dynamic items already represent None: adding default=None must preserve that result type.
from typing import Any

values: list[Any] = [3, 1]
empty: list[Any] = []
print(max(values, default=None), min(values, default=None))
print(max(empty, default=None), min(empty, default=None))
print(max(values, key=lambda x: -x, default=None), min(values, default=None, key=lambda x: -x))
print(max(empty, key=lambda x: -x, default=None))
fallback: Any = []
print(max(empty, default=fallback) is fallback)
print(max(values, default="empty"), min(empty, default="empty"))
