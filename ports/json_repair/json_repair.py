# pystachy: dynamic-any
# Pystachy port: in-memory, schema-free facade; retain upstream's valid-JSON
# fast path and parser options. File, CLI and schema APIs are not exposed.
import json
from typing import Any
from .json_parser import JSONParser


def repair_json(json_str: str = "", return_objects: bool = False,
                skip_json_loads: bool = False, logging: bool = False, *,
                stream_stable: bool = False, strict: bool = False,
                ensure_ascii: bool = True) -> Any:
    parsed_json: Any = None
    repair_log: list[Any] = []
    is_valid_json = False
    if not skip_json_loads:
        try:
            parsed_json = json.loads(json_str)
            is_valid_json = True
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    if not is_valid_json:
        parser = JSONParser(json_str, logging, stream_stable=stream_stable,
                            strict=strict, try_valid_json_suffix=True)
        parser.logger = repair_log
        try:
            parsed_json = parser.parse()
        except RecursionError as exc:
            raise ValueError("Input nesting exceeds the supported parser recursion depth.") from exc
    if logging:
        return parsed_json, repair_log
    if return_objects:
        return parsed_json
    if parsed_json == "":
        return ""
    return json.dumps(parsed_json, ensure_ascii=ensure_ascii)


def loads(json_str: str, skip_json_loads: bool = False, logging: bool = False,
          stream_stable: bool = False, strict: bool = False) -> Any:
    return repair_json(json_str, True, skip_json_loads, logging,
                       stream_stable=stream_stable, strict=strict)
