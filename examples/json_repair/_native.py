# pystachy: dynamic-any
import json
from ffi import export
from json_repair import loads as _loads, repair_json as _repair_json


@export
def repair_text(text: str, skip_json_loads: bool, stream_stable: bool, strict: bool, ensure_ascii: bool) -> str:
    result = _repair_json(text, skip_json_loads=skip_json_loads, stream_stable=stream_stable,
                          strict=strict, ensure_ascii=ensure_ascii)
    if isinstance(result, str):
        return result
    raise TypeError("Schema-free text repair must return a string")


@export
def load_payload(text: str, logging: bool, stream_stable: bool, strict: bool) -> str:
    result = _loads(text, skip_json_loads=True, logging=logging, stream_stable=stream_stable, strict=strict)
    # Preserve lone or adjacent surrogate code points through the str ABI:
    # encoding them as \u escapes can combine adjacent surrogates on CPython.
    return json.dumps(result, ensure_ascii=False)
