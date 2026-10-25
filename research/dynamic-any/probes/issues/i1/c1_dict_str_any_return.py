# pystachy: dynamic-any
from typing import Any

def make() -> Any:
    out: dict[str, Any] = {}
    out["a"] = 1
    return out


print(make())
