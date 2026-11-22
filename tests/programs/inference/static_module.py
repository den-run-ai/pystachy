# pystachy: static
"""A static module holds no Any value: typing.Any keeps its inference meaning, and closed unions
and typed JSON hold what is mixed. Everything here compiles as it does without the marker."""
from __future__ import annotations

import json
from typing import Any


def first(xs: list[Any]) -> Any:
    # (inferred from each call: no value is boxed)
    return xs[0]


def describe(value: json.JSONValue) -> str:
    if isinstance(value, dict):
        return "dict of " + str(len(value))
    if isinstance(value, list):
        return "list of " + str(len(value))
    return str(value)


def total(amounts: list[int | float]) -> float:
    t = 0.0
    for a in amounts:
        t += a
    return t


doc = json.loads('{"rows": [{"id": 1, "tags": ["a", "b"]}, {"id": 2.5}], "name": "demo"}')
print(first([1, 2]), first(["x"]), first([[1.5]]))
print(describe(doc), describe(doc["rows"]), describe(doc["name"]), describe(doc["rows"][1]["id"]))
doc["rows"][0]["tags"][1] = "c"
doc["count"] = 2
print(json.dumps(doc, sort_keys=True))
print(total([1, 2.5, 3]))
mixed: list[int | str | None] = [1, "two", None]
print(mixed, [type(x).__name__ for x in mixed])
