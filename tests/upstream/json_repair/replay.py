# pystachy: dynamic-any
"""Replay schema-free inputs through pristine/adapted CPython or native Pystachy.

Usage: native_parity.py inputs.jsonl
The host checker reads the tagged output; strings are code points so separate
surrogates cannot accidentally compare equal to one astral character.
"""
import json
import sys
from typing import Any

from json_repair import loads, repair_json


def tagged(value: Any) -> Any:
    if value is None:
        return ["none"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        # The host checker converts this representation to float.hex(), avoiding
        # a float.hex dependency in the prototype or false notation differences.
        return ["float-repr", repr(value)]
    if isinstance(value, str):
        codes: list[Any] = []
        for char in value:
            codes.append(ord(char))
        return ["str", codes]
    if isinstance(value, list):
        items: list[Any] = []
        for item in value:
            items.append(tagged(item))
        return ["list", items]
    if isinstance(value, tuple):
        elements: list[Any] = []
        for element in value:
            elements.append(tagged(element))
        return ["tuple", elements]
    if isinstance(value, dict):
        pairs: list[Any] = []
        for key in value:
            pairs.append([tagged(key), tagged(value[key])])
        return ["dict", pairs]
    raise TypeError("Unexpected repaired value type: " + type(value).__name__)


with open(sys.argv[1]) as source:
    for line in source:
        request: Any = json.loads(line)
        flags: Any = request["flags"]
        row: dict[str, Any] = {"id": request["id"]}
        try:
            result: Any = None
            if request.get("api", "repair_json") == "loads":
                result = loads(
                    request["input"],
                    skip_json_loads=flags.get("skip_json_loads", False),
                    logging=flags.get("logging", False),
                    stream_stable=flags.get("stream_stable", False),
                    strict=flags.get("strict", False),
                )
            else:
                result = repair_json(
                    request["input"],
                    return_objects=flags.get("return_objects", True),
                    skip_json_loads=flags.get("skip_json_loads", False),
                    logging=flags.get("logging", False),
                    stream_stable=flags.get("stream_stable", False),
                    strict=flags.get("strict", False),
                    ensure_ascii=flags.get("ensure_ascii", True),
                )
            row["value"] = tagged(result)
        except Exception as exc:
            row["error"] = type(exc).__name__
            row["message"] = str(exc)
        print(json.dumps(row))
