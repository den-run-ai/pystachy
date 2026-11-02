# pystachy: dynamic-any
# Integer tokens up to the 4,300-digit conversion limit stay integers. Beyond it,
# follow upstream json_repair on CPython: the valid-JSON fast path falls back to
# repair, the missing-brace probe declines, and the number parser keeps the token
# as text. The same port is the CPython oracle.
import json
from typing import Any
from json_repair import loads, repair_json


def describe(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join([describe(item) for item in value]) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join([key + ": " + describe(value[key]) for key in value]) + "}"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        # str() of more than 4,300 digits raises; json.dumps() checks the value.
        return "int(" + str(len(json.dumps(value))) + ")"
    if isinstance(value, str):
        return "str(" + str(len(value)) + ")"
    return type(value).__name__


def check(source: str, token: str, shape: str, skip: bool) -> None:
    result: Any = loads(source, skip_json_loads=skip, logging=True)
    value: Any = result[0]
    digits = len(token) - 1 if token.startswith("-") else len(token)
    if digits <= 4300:
        if shape == "array":
            value = value[0]
        elif shape != "root":
            value = value["n"]
        assert isinstance(value, int) and json.dumps(value) == token
    print(shape, skip, token[0] == "-", describe(result[0]), len(result[1]))


for negative in [False, True]:
    for length in [4300, 4301]:
        token = ("-" if negative else "") + "9" * length
        # Forced repair intentionally does not recognize top-level numbers.
        # Exercise those through the public default API instead.
        check(token, token, "root", False)
        for skip in [False, True]:
            check('{"n":' + token + '}', token, "object", skip)
            check('[' + token + ']', token, "array", skip)
            check('"n":' + token + '}', token, "missing brace", skip)

# upstream's test_missing_opening_brace_declines_integer_conversion_limit
assert loads('"a": ' + "1" * 4301 + "}", logging=True) == ("", [])

# A malformed object reaches parse_number even with default fast-path selection.
token = "9" * 4301
for skip in [False, True]:
    print(repr(repair_json('{n:' + token + ',}', skip_json_loads=skip))[:12])
print(repr(repair_json(token)), repr(repair_json("-" + token)))
