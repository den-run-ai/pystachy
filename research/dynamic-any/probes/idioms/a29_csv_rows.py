# pystachy: dynamic-any
# csv.DictWriter of mixed rows into a StringIO
import csv
import io
from typing import Any

rows: list[dict[str, Any]] = [{"id": 1, "name": "a", "score": 2.5}, {"id": 2, "name": "b", "score": None}]
buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=["id", "name", "score"])
w.writeheader()
for r in rows:
    w.writerow(r)
print(buf.getvalue(), end="")
