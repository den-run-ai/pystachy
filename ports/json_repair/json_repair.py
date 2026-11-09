# pystachy: dynamic-any
# Pystachy port: in-memory, schema-free facade; retain upstream's valid-JSON
# fast path and parser options. File wrappers and schema APIs are excluded.
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
    invalid_root = False
    if not skip_json_loads:
        try:
            parsed_json = json.loads(json_str)
            is_valid_json = True
        except json.JSONDecodeError as error:
            # Extra data can follow a valid initial value.
            invalid_root = error.msg != "Extra data"
        except (TypeError, ValueError):
            pass
    if not is_valid_json:
        parser = JSONParser(json_str, logging, stream_stable=stream_stable,
                            strict=strict, try_valid_json_suffix=True)
        if type(json_str) is str and json_str.startswith(("{", "[")):
            # A bare object key is also conclusive when validation was skipped.
            if invalid_root or (json_str[0] == "{" and len(json_str) > 1 and json_str[1] not in '"} \t\r\n'):
                # Object repair can replace the parser's source before a second root.
                parser._deferred_initial_source = json_str
        parser.logger = repair_log
        try:
            parsed_json = parser.parse()
        except RecursionError as exc:
            raise ValueError("Input nesting exceeds the supported parser recursion depth.") from exc
    if logging:
        return parsed_json, repair_log
    if return_objects:
        return parsed_json
    # Preserve the empty result used when repair could not find a value.
    if parsed_json == "" and not is_valid_json:
        return ""
    return json.dumps(parsed_json, ensure_ascii=ensure_ascii)


def loads(json_str: str, skip_json_loads: bool = False, logging: bool = False,
          stream_stable: bool = False, strict: bool = False) -> Any:
    return repair_json(json_str, True, skip_json_loads, logging,
                       stream_stable=stream_stable, strict=strict)
