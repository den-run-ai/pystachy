# pystachy: dynamic-any
# str.format(**record) and %-formatting with a mapping of Any values
from typing import Any

rec: dict[str, Any] = {"name": "cpu", "value": 42, "ratio": 0.25}
print("{name}={value} ({ratio:.0%})".format(**rec))
print("%(name)s=%(value)d" % rec)
