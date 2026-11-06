# pystachy: dynamic-any
from typing import Any

rows: list[tuple[str, Any]] = []
k: Any = "a"
rows.append((k, 1))
print(rows)
