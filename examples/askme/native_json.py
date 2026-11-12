"""JSON values shared by the native AskMe modules.

The harness keeps model replies, step records and run state as plain JSON
values, exactly like ``askme.py``. One recursive alias names that closed set of
types so the same source runs on CPython and PyPy, type-checks under mypy, and
compiles with mypyc and Pystachy. Pystachy supplies its own native alias; the
other runtimes use the equivalent ``typing`` spelling.
"""

from __future__ import annotations

import json
import sys
from typing import Dict, List, Union

if sys.implementation.name != "pystachy":
    JSONValue = Union[None, bool, int, float, str, List["JSONValue"], Dict[str, "JSONValue"]]
else:
    from json import JSONValue  # type: ignore


def truthy(value: JSONValue) -> bool:
    """Python truthiness of one decoded JSON value."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, float):
        return value != 0.0
    if isinstance(value, str):
        return len(value) > 0
    if isinstance(value, list):
        return len(value) > 0
    return len(value) > 0


def get_str(obj: dict[str, JSONValue], key: str, default: str = "") -> str:
    """``obj.get(key, default)`` for a field whose stored value is a string."""
    value = obj.get(key)
    if isinstance(value, str):
        return value
    return default


def get_int(obj: dict[str, JSONValue], key: str, default: int = 0) -> int:
    value = obj.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default


def get_flag(obj: dict[str, JSONValue], key: str) -> bool:
    """Truthiness of ``obj.get(key)``."""
    return truthy(obj.get(key))


def get_list(obj: dict[str, JSONValue], key: str) -> list[JSONValue]:
    """The list stored at ``key``; an absent or non-list value reads as empty."""
    value = obj.get(key)
    if isinstance(value, list):
        return value
    empty: list[JSONValue] = []
    return empty


def get_dict(obj: dict[str, JSONValue], key: str) -> dict[str, JSONValue]:
    """The object stored at ``key``; an absent or non-object value reads as empty."""
    value = obj.get(key)
    if isinstance(value, dict):
        return value
    empty: dict[str, JSONValue] = {}
    return empty


def as_dict(value: JSONValue) -> dict[str, JSONValue]:
    """Narrow a value known to be an object; anything else reads as empty."""
    if isinstance(value, dict):
        return value
    empty: dict[str, JSONValue] = {}
    return empty


def as_str(value: JSONValue, default: str = "") -> str:
    if isinstance(value, str):
        return value
    return default


def str_items(values: list[str]) -> list[JSONValue]:
    """A JSON array holding the given strings."""
    out: list[JSONValue] = []
    for value in values:
        out.append(value)
    return out


def json_copy(value: JSONValue) -> JSONValue:
    """Detached copy of a JSON value (``copy.deepcopy`` for this value set)."""
    if isinstance(value, list):
        items: list[JSONValue] = []
        for item in value:
            items.append(json_copy(item))
        return items
    if isinstance(value, dict):
        fields: dict[str, JSONValue] = {}
        for key, item in value.items():
            fields[key] = json_copy(item)
        return fields
    return value


def copy_dict(value: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """``dict(value)``: a new object sharing the same member values."""
    fields: dict[str, JSONValue] = {}
    for key, item in value.items():
        fields[key] = item
    return fields


def _pretty(value: JSONValue, level: int, out: list[str]) -> None:
    # Scalars are written here: an encoder call per leaf dominated large results.
    if value is None:
        out.append("null")
        return
    if isinstance(value, bool):
        out.append("true" if value else "false")
        return
    if isinstance(value, int):
        out.append(str(value))
        return
    if isinstance(value, list):
        if not value:
            out.append("[]")
            return
        inner = "\n" + "  " * (level + 1)
        out.append("[")
        first = True
        for item in value:
            out.append(inner if first else "," + inner)
            first = False
            _pretty(item, level + 1, out)
        out.append("\n" + "  " * level + "]")
        return
    if isinstance(value, dict):
        if not value:
            out.append("{}")
            return
        inner = "\n" + "  " * (level + 1)
        out.append("{")
        first = True
        for key, item in value.items():
            out.append(inner if first else "," + inner)
            first = False
            out.append(json.dumps(key))
            out.append(": ")
            _pretty(item, level + 1, out)
        out.append("\n" + "  " * level + "}")
        return
    out.append(json.dumps(value))


def dumps_pretty(value: JSONValue) -> str:
    """``json.dumps(value, indent=2)`` for JSON values."""
    out: list[str] = []
    _pretty(value, 0, out)
    return "".join(out)
