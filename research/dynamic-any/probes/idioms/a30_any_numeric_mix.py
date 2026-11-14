# pystachy: dynamic-any
# numeric fields that are usually ints but sometimes floats, strings or missing
from typing import Any

recs: list[Any] = [{"amount": 7}, {"amount": 2.5}, {"amount": "n/a"}, {}, {"amount": 3}, {"amount": None}]
total: Any = 0
bad = 0
for r in recs:
    a = r.get("amount")
    if isinstance(a, (int, float)) and not isinstance(a, bool):
        total += a
    else:
        bad += 1
print(total, bad)
