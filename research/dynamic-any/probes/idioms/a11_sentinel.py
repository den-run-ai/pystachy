# pystachy: dynamic-any
# an object() sentinel to tell a missing argument from None
from typing import Any

_MISSING: Any = object()


def get(d: dict[str, Any], key: str, default: Any = _MISSING) -> Any:
    if key in d:
        return d[key]
    if default is _MISSING:
        raise KeyError(key)
    return default


d: dict[str, Any] = {"a": 1, "b": None}
print(get(d, "a"), get(d, "b"), get(d, "c", "dflt"))
try:
    get(d, "c")
except KeyError as e:
    print("KeyError", e)
