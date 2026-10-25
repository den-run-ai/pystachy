# pystachy: dynamic-any
from collections.abc import Sequence
from typing import Any


def kind(v: Any) -> str:
    if isinstance(v, Sequence) and not isinstance(v, str):
        return "sequence"
    return "other"


print(kind([1]), kind((1, 2)), kind("s"))
