# pystachy: dynamic-any
from typing import Any

s: Any = "hello world"
xs: Any = [1, "two", 3.0]
print(s[:5], s[6:], xs[1:], xs[::-1])
