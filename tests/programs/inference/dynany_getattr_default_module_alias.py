# pystachy: dynamic-any
# A module alias must not hide the exception frame needed by getattr's default.
import builtins as b
from typing import Any

value: Any = 42
print(b.getattr(value, "n", None))
