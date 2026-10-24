# pystachy: dynamic-any
# sum() of a generator of Any values
from typing import Any

rows: list[Any] = [{"t": 3}, {"t": 21.5}, {"t": 18}]
print(sum(r["t"] for r in rows), sum([r["t"] for r in rows]))
