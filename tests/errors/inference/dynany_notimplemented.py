# error: a NotImplementedType value cannot become an Any value
# pystachy: dynamic-any
from typing import Any


def decline() -> Any:
    return NotImplemented


print(decline())
