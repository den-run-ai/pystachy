# pystachy: dynamic-any
# Digit-limit failures are not malformed JSON: do not retry them as repairable
# text or silently change an integer to a string. The same port is the CPython oracle.
import json
from typing import Any
from json_repair import loads, repair_json


def check(source: str, token: str, shape: str, skip: bool, too_long: bool) -> None:
    try:
        value: Any = loads(source, skip_json_loads=skip)
    except ValueError as exc:
        assert too_long
        assert "Exceeds the limit" in str(exc)
        print(shape, skip, token[0] == "-", "ValueError")
    else:
        assert not too_long
        if shape == "array":
            value = value[0]
        elif shape != "root":
            value = value["n"]
        assert isinstance(value, int)
        assert json.dumps(value) == token
        print(shape, skip, token[0] == "-", "integer preserved")


for negative in [False, True]:
    for length in [4300, 4301]:
        token = ("-" if negative else "") + "9" * length
        # Forced repair intentionally does not recognize top-level numbers.
        # Exercise those through the public default API instead.
        check(token, token, "root", False, length > 4300)
        for skip in [False, True]:
            check('{"n":' + token + '}', token, "object", skip, length > 4300)
            check('[' + token + ']', token, "array", skip, length > 4300)
            check('"n":' + token + '}', token, "missing brace", skip, length > 4300)

# A malformed object reaches parse_number even with default fast-path selection.
token = "9" * 4301
for skip in [False, True]:
    check('{n:' + token + ',}', token, "repair", skip, True)
try:
    repair_json(token)
except ValueError as exc:
    assert "Exceeds the limit" in str(exc)
    print("serialized root ValueError")
else:
    raise AssertionError("oversized root integer disappeared")
