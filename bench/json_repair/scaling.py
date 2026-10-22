# pystachy: dynamic-any
"""Payload-size probes for JSON repair: MODE SIZE ROUNDS (default: comma 1000 20).

Compare the witness lines across implementations before comparing seconds.
Size counts repeated fragments, not bytes. Startup, compilation, input creation
and exact-result validation are outside the timer. Use ROUNDS=0 for validation.
"""
import sys
from time import perf_counter
from typing import Any

from json_repair import repair_json


def payload(mode: str, size: int) -> tuple[str, str]:
    if mode == "valid":
        value = "x," * size
        return '{"a":"' + value + '"}', value
    if mode == "comma":
        value = "x," * size
        return '{"a": "' + value + '" tail', value
    if mode == "newline":
        value = "line\n" * size + "end"
        return '{"a":"' + value + '"}', value
    if mode == "unicode":
        value = "é🌲," * size
        return '{"a":"' + value + '",}', value
    if mode == "escaped":
        return '{"a":"' + "x\\n" * size + 'end",}', "x\n" * size + "end"
    if mode == "logs":
        value = "x," * size
        return '{a: "' + value + '",}', value
    raise ValueError("mode must be valid, comma, newline, unicode, escaped or logs")


def checked_value(result: Any, expected: str, logging: bool) -> int:
    logs = 0
    value: Any = result
    if logging:
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError("expected result and repair-log tuple")
        value = result[0]
        log: Any = result[1]
        if not isinstance(log, list):
            raise ValueError("expected repair-log list")
        for entry in log:
            if not isinstance(entry, dict) or len(entry) != 2:
                raise ValueError("unexpected log record")
            if not isinstance(entry["text"], str) or not isinstance(entry["context"], str):
                raise ValueError("unexpected log field type")
        logs = len(log)
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("expected exactly one object member")
    text: Any = value["a"]
    if not isinstance(text, str) or text != expected:
        raise ValueError("repair changed the expected payload")
    return logs


mode = sys.argv[1] if len(sys.argv) > 1 else "comma"
size = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 20
if size < 1 or rounds < 0:
    raise ValueError("size must be positive and rounds nonnegative")
source, expected = payload(mode, size)
logging = mode == "logs"
result: Any = repair_json(source, return_objects=True, logging=logging)
log_count = checked_value(result, expected, logging)
print("witness", mode, size, len(source), len(expected), log_count)
start = perf_counter()
for _ in range(rounds):
    result = repair_json(source, return_objects=True, logging=logging)
seconds = perf_counter() - start
if checked_value(result, expected, logging) != log_count:
    raise ValueError("repair log count changed across repeated calls")
print("rounds", rounds)
print("seconds", seconds)
