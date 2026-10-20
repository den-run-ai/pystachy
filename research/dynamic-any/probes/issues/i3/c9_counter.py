# pystachy: dynamic-any
from collections import Counter
from typing import Any

events: list[Any] = [{"k": "a"}, {"k": "b"}, {"k": "a"}]
print(Counter(e["k"] for e in events).most_common())
