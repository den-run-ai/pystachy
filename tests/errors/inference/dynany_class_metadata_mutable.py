# error: class values with mutable C.__module__ are not supported
# pystachy: dynamic-any
from typing import Any


class C:
    __module__ = "before"


C.__module__ = "after"
cls: Any = C
print(cls.__module__)
