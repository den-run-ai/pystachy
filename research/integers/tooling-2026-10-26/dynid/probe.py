# pystachy: dynamic-any
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


same("masked operators", (1000 + 23) & 1000, 1000)
same("masked shift", (125 << 3) & 1023, 1000)
same("masked nested", ((40 * 25) | 7) & ~7, 1000)
