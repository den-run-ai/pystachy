# pystachy: dynamic-any
# an explicit conversion from json.loads()'s JSONValue to Any storage, and back
from __future__ import annotations

import json
from typing import Any


def to_any(v: json.JSONValue) -> Any:
    if isinstance(v, dict):
        d: dict[Any, Any] = {}
        for k, x in v.items():
            d[k] = to_any(x)
        return d
    if isinstance(v, list):
        out: list[Any] = []
        for x in v:
            out.append(to_any(x))
        return out
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        return v
    return None


def to_json(x: Any) -> json.JSONValue:
    if isinstance(x, dict):
        d: dict[str, json.JSONValue] = {}
        for k in x:
            d[str(k)] = to_json(x[k])
        return d
    if isinstance(x, list) or isinstance(x, tuple):
        out: list[json.JSONValue] = []
        for e in x:
            out.append(to_json(e))
        return out
    if isinstance(x, bool):
        return bool(x)
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        return float(x)
    if isinstance(x, str):
        return str(x)
    if x is None:
        return None
    raise TypeError("not JSON serializable: " + type(x).__name__)


doc = to_any(json.loads('{"a": [1, "two", {"b": null}], "n": 2.5, "ok": true}'))
print(doc["a"][1], doc["n"] * 2, doc["a"][2]["b"], doc["ok"])
doc["a"].append({"c": [3, 4.5]})
doc["extra"] = (1, "x")
print(json.dumps(to_json(doc), sort_keys=True))
