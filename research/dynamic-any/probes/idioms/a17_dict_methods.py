# pystachy: dynamic-any
# dict methods on an Any dict: get, setdefault, pop, update, items, copy
from typing import Any

d: Any = {"a": 1, "b": "two"}
d.setdefault("c", [])
d["c"].append(3.5)
d.update({"e": None})
print(d.pop("a"), d.get("z", "none"), sorted(d.keys()))
print(d)
e = d.copy()
e["b"] = 2
print(d["b"], e["b"])
