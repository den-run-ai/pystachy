# pystachy: dynamic-any
"""A copy module for builtin values held as Any (an experiment): dicts, lists, tuples, scalars."""
from typing import Any


class Error(Exception):
    pass


error = Error


def _deep(x: Any, memo: dict[int, Any]) -> Any:
    if x is None or isinstance(x, bool) or isinstance(x, int) or isinstance(x, float) or isinstance(x, str):
        return x
    k = id(x)
    if k in memo:
        return memo[k]
    if isinstance(x, list):
        y: list[Any] = []
        memo[k] = y
        for item in x:
            y.append(_deep(item, memo))
        return y
    if isinstance(x, dict):
        d: dict[Any, Any] = {}
        memo[k] = d
        for key in x:
            d[_deep(key, memo)] = _deep(x[key], memo)
        return d
    if isinstance(x, tuple):
        items: list[Any] = []
        for item in x:
            items.append(_deep(item, memo))
        t = tuple(items)
        memo[k] = t
        return t
    raise Error("un(deep)copyable object of type " + type(x).__name__)


def deepcopy(x: Any, memo: Any = None) -> Any:
    m: dict[int, Any] = {}
    return _deep(x, m)


def copy(x: Any) -> Any:
    if isinstance(x, list):
        y: list[Any] = []
        for item in x:
            y.append(item)
        return y
    if isinstance(x, dict):
        d: dict[Any, Any] = {}
        for key in x:
            d[key] = x[key]
        return d
    return x
