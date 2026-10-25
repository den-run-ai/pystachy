# pystachy: dynamic-any
# **kwargs: Any options and *args: Any
from typing import Any


def make(kind: str, **opts: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"kind": kind}
    for k, v in opts.items():
        d[k] = v
    return d


def total(*xs: Any) -> Any:
    t: Any = 0
    for x in xs:
        t = t + x
    return t


print(make("job", retries=3, name="x", ratio=0.5))
print(total(1, 2.5, True), total(3, -1))
