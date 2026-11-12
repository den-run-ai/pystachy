# pystachy: dynamic-any
# pystachy: python-int
# json.JSONDecoder().raw_decode() decodes into Any storage where its result is declared so.
import json
from typing import Any


def direct(s: str) -> tuple[Any, int]:
    return json.JSONDecoder().raw_decode(s)


def unpacked(s: str) -> tuple[bool, Any]:
    value: Any
    end: int
    try:
        value, end = json.JSONDecoder().raw_decode(s)
    except json.JSONDecodeError:
        return False, ""
    return end > 0, value


def typed(s: str) -> int:
    value, end = json.JSONDecoder().raw_decode(s)
    return end


v, e = direct('{"a": [1, 123456789012345678901234567890]} tail')
v["a"].append("x")
print(v, e)
print(unpacked('[1, 2] rest'))
print(typed('[1, 2] rest'))
try:
    direct("nope")
except json.JSONDecodeError as err:
    print("error", err.msg, err.pos)
