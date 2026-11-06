# pystachy: dynamic-any
# toolz-style get_in with functools.reduce and operator.getitem
import operator
from functools import reduce
from typing import Any


def get_in(keys: list[Any], coll: Any, default: Any = None) -> Any:
    try:
        return reduce(operator.getitem, keys, coll)
    except (KeyError, IndexError, TypeError):
        return default


doc = {"a": [{"b": 1}, {"b": "two"}], "c": 3}
print(get_in(["a", 1, "b"], doc), get_in(["a", 5], doc, "none"), get_in(["c"], doc))
