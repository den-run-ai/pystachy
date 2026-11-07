# pystachy: dynamic-any
# Both omitted and supplied arms may be unsupported for a dormant parameter.
from typing import Any


def unavailable(values: list[str] = "unused", marker: int = 1) -> int:
    return len(values) + marker


def identity(value: int) -> int:
    return value


saved: Any = unavailable
function: Any = identity
args: Any = [5]
keywords: Any = {}
print(function(*args, **keywords), saved is unavailable)
