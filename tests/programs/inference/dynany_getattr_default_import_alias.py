# pystachy: dynamic-any
# An imported alias must discover the handler needed for a missing attribute.
from builtins import getattr as pick
from typing import Any

value: Any = 42
print(pick(value, "n", None))
