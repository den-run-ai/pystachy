# pystachy: dynamic-any
# Qualified getattr needs its own handler, without a direct getattr call nearby.
import builtins
from typing import Any

value: Any = 42
print(builtins.getattr(value, "n", None))
