# pystachy: dynamic-any
from typing import Any

original: Any = float("nan")
value: float = original
values: tuple[float | None, ...] = (value, None, value)
print(value in values)
