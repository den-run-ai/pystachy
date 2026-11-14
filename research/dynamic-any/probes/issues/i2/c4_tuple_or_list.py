# pystachy: dynamic-any
from typing import Any

def first(obj: tuple | list) -> Any:
    return obj[0]


print(first([1, "a"]))
