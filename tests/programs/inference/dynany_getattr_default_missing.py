# pystachy: dynamic-any
# A missing dynamic attribute needs its own exception frame, even with no
# property, comparison method or explicit try/except anywhere in the program.
from typing import Any

value: Any = 42
print(getattr(value, "n", None))
print(getattr(value, "n", 7))
