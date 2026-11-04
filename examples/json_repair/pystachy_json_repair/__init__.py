"""Call the native schema-free repair port from its importing CPython thread."""
import json
import re

from . import _native


_decode = json.JSONDecoder().raw_decode
_whitespace = re.compile(r"[ \t\r\n]*").match


def loads(json_str: str, skip_json_loads: bool = False, logging: bool = False,
          stream_stable: bool = False, strict: bool = False):
    if not skip_json_loads and type(json_str) is str:
        # raw_decode reads one value. Multiple roots and trailing non-JSON
        # whitespace still need the repair parser.
        try:
            start = _whitespace(json_str).end() if json_str and json_str[0] in " \t\r\n" else 0
            value, end = _decode(json_str, start)
            if end == len(json_str) or _whitespace(json_str, end).end() == len(json_str):
                return (value, []) if logging else value
        except ValueError:
            pass
    elif not skip_json_loads and isinstance(json_str, str):
        # A str subclass may override indexing; preserve CPython decoder behavior.
        try:
            value = json.loads(json_str)
        except ValueError:
            pass
        else:
            return (value, []) if logging else value

    payload = _native.load_payload(json_str, logging, stream_stable, strict)
    value, end = _decode(payload)
    if end != len(payload):
        raise ValueError("Unexpected trailing data in native JSON payload")
    return tuple(value) if logging else value


def repair_json(json_str: str = "", return_objects: bool = False, skip_json_loads: bool = False,
                logging: bool = False, *, stream_stable: bool = False, strict: bool = False,
                ensure_ascii: bool = True):
    if return_objects or logging:
        return loads(json_str, skip_json_loads, logging, stream_stable, strict)
    return _native.repair_text(json_str, skip_json_loads, stream_stable, strict, ensure_ascii)
