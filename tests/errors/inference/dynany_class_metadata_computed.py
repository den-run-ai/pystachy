# error: class values with nonliteral C.__module__ are not supported
# pystachy: dynamic-any
from typing import Any


class C:
    __module__ = "w" + "ire"


cls: Any = C
print(cls.__module__)
