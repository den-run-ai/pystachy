# error: class values with mutable C.__name__ are not supported
# pystachy: dynamic-any
from typing import Any


class C:
    __name__ = "Original"


C.__name__ = "Changed"
cls: Any = C
print(cls.__name__, repr(cls))
