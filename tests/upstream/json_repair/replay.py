# pystachy: dynamic-any
"""Replay inputs, with or without a schema, through pristine/adapted CPython or native Pystachy.

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
        text: str = request["input"]
        if "input_codepoints" in request:
            # JSON transport otherwise combines literal adjacent surrogates.
            characters: list[str] = []
            for code in request["input_codepoints"]:
                characters.append(chr(int(code)))
            text = "".join(characters)
        flags: Any = request["flags"]
        row: dict[str, Any] = {"id": request["id"]}
        try:
            result: Any = None
            # A schema's options are passed only with a schema: the CPython companion extension,
            # which replays the schema-free corpus through this program, takes neither.
            if request.get("api", "repair_json") == "loads":
                if "schema" in flags:
                    result = loads(
                        text,
                        skip_json_loads=flags.get("skip_json_loads", False),
                        logging=flags.get("logging", False),
                        stream_stable=flags.get("stream_stable", False),
                        strict=flags.get("strict", False),
                        schema=flags.get("schema"),
                        schema_repair_mode=flags.get("schema_repair_mode", "standard"),
                    )
                else:
                    result = loads(
                        text,
                        skip_json_loads=flags.get("skip_json_loads", False),
                        logging=flags.get("logging", False),
                        stream_stable=flags.get("stream_stable", False),
                        strict=flags.get("strict", False),
                    )
            elif "schema" in flags:
                result = repair_json(
                    text,
                    return_objects=flags.get("return_objects", True),
                    skip_json_loads=flags.get("skip_json_loads", False),
                    logging=flags.get("logging", False),
                    stream_stable=flags.get("stream_stable", False),
                    strict=flags.get("strict", False),
                    ensure_ascii=flags.get("ensure_ascii", True),
                    schema=flags.get("schema"),
                    schema_repair_mode=flags.get("schema_repair_mode", "standard"),
                )
            else:
                result = repair_json(
                    text,
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
