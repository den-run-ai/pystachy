# pystachy: dynamic-any
# Integer queries of boxed-key tables retain the pure probe and boxed fallback.
# The fallback reuses the parameter's incoming box, or boxes once a new number that
# its caller passed without one (a null companion).
# Ordinary typed dicts and queries that are already Any keep their existing path.
from typing import Any


def contains(d: dict[int, Any], k: int) -> bool:
    return k in d


def getitem(d: dict[int, Any], k: int) -> Any:
    return d[k]


def typed_contains(d: dict[int, int], k: int) -> bool:
    return k in d


def typed_getitem(d: dict[int, int], k: int) -> int:
    return d[k]


def dynamic_contains(d: dict[Any, Any], k: Any) -> bool:
    return k in d


def dynamic_getitem(d: dict[Any, Any], k: Any) -> Any:
    return d[k]
