# pystachy: dynamic-any
# datetime values in Any storage, as a TOML document's tables hold them (tomllib), compare as
# CPython's do: with each other through their methods, and with values of other types, which
# lib/datetime.py's methods (annotated with their classes) decline, so that documents compare as
# False rather than raising (#772)
from datetime import date, datetime, time
from typing import Any

doc: Any = {"when": datetime(2020, 1, 2, 3, 4, 5), "day": date(2020, 1, 2), "at": time(3, 4), "n": 1}
same: Any = {"when": datetime(2020, 1, 2, 3, 4, 5), "day": date(2020, 1, 2), "at": time(3, 4), "n": 1}
other: Any = {"when": "2020-01-02T03:04:05", "day": date(2020, 1, 3), "at": None, "n": 1}
print(doc == same, doc == other, doc != other, other == doc)
for k in ["when", "day", "at"]:
    print(k, doc[k] == same[k], doc[k] == other[k], other[k] == doc[k], doc[k] != other[k], doc[k] in [other[k]], other[k] in [doc[k]])
w: Any = doc["when"]
d: Any = doc["day"]
print(w == d, d == w, w != d, w == "x", "x" == w, w == 1, w < datetime(2021, 1, 1), d < date(2020, 1, 1))
