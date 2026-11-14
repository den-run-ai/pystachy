# pystachy: dynamic-any
# deep-merge configuration documents (mergedeep/deepmerge style)
from typing import Any


def merge(a: Any, b: Any) -> Any:
    if isinstance(a, dict) and isinstance(b, dict):
        out: dict[str, Any] = {}
        for k in a:
            out[k] = a[k]
        for k in b:
            out[k] = merge(out[k], b[k]) if k in out else b[k]
        return out
    return b


base = {"db": {"host": "localhost", "port": 5432, "opts": {"ssl": False}}, "debug": False}
over = {"db": {"port": 6543, "opts": {"ssl": True, "timeout": 2.5}}, "name": "app"}
print(merge(base, over))
