# pystachy: dynamic-any
from collections.abc import Mapping
from typing import Any


def kind(v: Any) -> str:
    if isinstance(v, Mapping):
        return "mapping"
    return "other"


print(kind({"a": 1}), kind([1]))
