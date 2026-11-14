# pystachy: dynamic-any
# re on an Any string
import re
from typing import Any

s: Any = "id=42 name=bob"
m = re.search(r"id=(\d+)", s)
print(m.group(1) if m else None, re.sub(r"\d", "#", s))
