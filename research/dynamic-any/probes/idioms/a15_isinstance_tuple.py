# pystachy: dynamic-any
# isinstance with a tuple of classes on Any values
from typing import Any

vals: list[Any] = [1, 2.5, "s", [1], {"a": 1}, None, True, (1, 2)]
for v in vals:
    print(isinstance(v, (int, float)), isinstance(v, (list, tuple)), isinstance(v, (str, dict)))
