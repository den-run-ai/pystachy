# pystachy: dynamic-any
# exceptions carrying Any values in their messages
from typing import Any


def check(x: Any) -> Any:
    if isinstance(x, int) and x < 0:
        raise ValueError(f"negative: {x!r}")
    if isinstance(x, str):
        raise TypeError("bad value " + repr(x))
    return x


for v in [1, -2, "s", 2.5]:
    try:
        print(check(v))
    except (ValueError, TypeError) as e:
        print(type(e).__name__, e)
