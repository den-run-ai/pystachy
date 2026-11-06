# pystachy: dynamic-any
# sorting records by a tuple key with mixed field types, and sorted() of an Any list
from typing import Any

rows: list[Any] = [{"g": "b", "n": 2}, {"g": "a", "n": 3.5}, {"g": "a", "n": 1}]
print([r["n"] for r in sorted(rows, key=lambda r: (r["g"], r["n"]))])
v: Any = [3, 1.5, 2]
print(sorted(v), sorted(v, reverse=True), min(v), max(v))
