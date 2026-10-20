# pystachy: dynamic-any
from typing import Any

rows: list[Any] = [{"t": 3}, {"t": 21.5}, {"t": 18}]
ts = [r["t"] for r in rows]
print(sum(ts), max(ts))
