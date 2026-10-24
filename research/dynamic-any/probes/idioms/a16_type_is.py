# pystachy: dynamic-any
# type(x) is int and type(x) == float tests on Any values
from typing import Any

vals: list[Any] = [1, 2.5, "s", True]
for v in vals:
    print(type(v) is int, type(v) == float, type(v) is bool)  # noqa: E721 (== of type objects is what it tests)
