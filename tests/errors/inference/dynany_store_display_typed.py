# error: an Any value cannot be used as dict[str,int] (narrow it with isinstance() first)
# pystachy: dynamic-any
# (a display stored into an Any value's attribute holds Any values: a field of typed items
# cannot take it, as before, when the display could not be typed)
from typing import Any


class P:
    def __init__(self) -> None:
        self.x: dict[str, int] = {"a": 1}


p: Any = P()
p.x = {}
print(p.x)
