# typing.Any in annotations that are never evaluated (from __future__ import annotations), where
# only type checkers import it, as tomli-w's do: a parameter or return it annotates is still left
# to each call
from __future__ import annotations

from collections.abc import Mapping

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any


def keys(table: Mapping[str, Any]) -> list[str]:
    return sorted(table)


def is_pair(obj: Any) -> bool:
    return isinstance(obj, tuple) and len(obj) == 2


def wrap(x: Any) -> dict[str, Any]:
    return {"value": x}


print(keys({"b": 1, "a": 2}), keys({"x": "y"}), is_pair((1, 2)), is_pair([1]))
print(wrap(1), wrap("s"))
