# pystachy: dynamic-any
from typing import Any


class Point:
    pass


p: Any = Point()
print(type(p).__qualname__)
