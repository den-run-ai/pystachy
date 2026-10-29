# pystachy: dynamic-any
# Capturing getattr before calling it still needs the default's exception frame.
from typing import Any

value: Any = 42
pick = getattr
print(pick(value, "n", None))
