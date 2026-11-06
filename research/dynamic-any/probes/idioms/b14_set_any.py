# pystachy: dynamic-any
# a set of Any values: dedup of mixed keys
from typing import Any

vals: list[Any] = [1, "a", 1, 2.5, "a", None]
seen: set[Any] = set()
out: list[Any] = []
for v in vals:
    if v not in seen:
        seen.add(v)
        out.append(v)
print(out)
