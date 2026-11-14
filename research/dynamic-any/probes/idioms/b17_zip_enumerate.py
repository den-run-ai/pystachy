# pystachy: dynamic-any
# zip, enumerate, dict comprehension and unpacking over Any rows
from typing import Any

header: Any = ["id", "name", "score"]
rows: Any = [[1, "a", 2.5], [2, "b", None]]
recs = [dict(zip(header, r)) for r in rows]
print(recs)
for i, (a, b, c) in enumerate(rows):
    print(i, a, b, c)
print({k: v for k, v in zip(header, rows[0])})
