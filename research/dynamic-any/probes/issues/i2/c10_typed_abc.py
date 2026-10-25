# pystachy: dynamic-any
from collections.abc import Mapping, Sequence


def kind(v):
    if isinstance(v, Mapping):
        return "mapping"
    if isinstance(v, Sequence):
        return "sequence"
    return "other"


print(kind({"a": 1}), kind([1]), kind(3))
