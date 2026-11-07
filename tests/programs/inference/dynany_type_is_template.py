# pystachy: dynamic-any
# Native specializations retain one canonical Python class identity.
from typing import Any


class Box:
    def __init__(self, v):
        self.v = v


x: Any = Box(1)
y: Any = Box("two")
print(type(x) is Box)
print(type(y) is Box, type(x) is type(y))
