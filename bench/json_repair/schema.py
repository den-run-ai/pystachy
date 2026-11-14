# pystachy: dynamic-any
"""JSON Schema consumer timings with exact results and first-error messages.

MODE ROUNDS [BATCHES WARMUPS]. Inputs, validator construction, complete-result
checks and printing stay outside the timer. Each round makes four public calls.
schema_upstream.py runs this same source with jsonschema's public imports.
"""
import json
import sys
from time import perf_counter
from typing import Any

from json_repair import repair_json
from json_repair._jsonschema.exceptions import SchemaError, ValidationError
from json_repair._jsonschema.validators import validator_for


SCHEMA: Any = json.loads('''{
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "tool": {"enum": ["search", "lookup"]},
        "count": {"type": "integer", "minimum": 0, "maximum": 1000},
        "scores": {"type": "array", "minItems": 1, "maxItems": 32,
                   "items": {"$ref": "#/$defs/score"}}
    },
    "required": ["tool", "count", "scores"],
    "additionalProperties": false,
    "$defs": {"score": {"type": "number", "minimum": 0, "maximum": 1}}
}''')
VALID: list[Any] = [
    {"tool": "search", "count": 3, "scores": [0.25, 0.5, 1.0]},
    {"tool": "lookup", "count": 0, "scores": [0.0]},
    {"tool": "search", "count": 15, "scores": [0.5] * 16},
    {"tool": "lookup", "count": 1000, "scores": [1.0] * 32},
]
EARLY: list[Any] = [1, [], True, None]
LATE: list[Any] = [
    {"tool": "search", "count": 3, "scores": [0.25, 0.5, 1.5]},
    {"tool": "lookup", "count": 0, "scores": [-0.5]},
    {"tool": "search", "count": 15, "scores": [0.5] * 15 + [2.0]},
    {"tool": "lookup", "count": 1000, "scores": [1.0] * 31 + ["bad"]},
]
MIXED: list[Any] = [VALID[0], EARLY[0], VALID[2], LATE[2]]
CHECKED: list[Any] = [SCHEMA, {"type": "integer"}, {"type": "strin"}, {"minItems": -1}]
REPAIR_SCHEMA: Any = json.loads('''{
    "type": "object",
    "properties": {
        "count": {"type": "integer", "minimum": 0, "default": 0},
        "name": {"type": "string", "default": ""},
        "active": {"type": "boolean", "default": false}
    },
    "required": ["count", "name", "active"],
    "additionalProperties": false
}''')
REPAIR_TEXT: list[str] = [
    '{count: "3", name: "alpha", active: "true"}',
    '{"count":4,"name":"beta","active":false}',
    "{count: 5, name: 'gamma', active: True,}",
    '{"count":"6","name":"delta","active":"false"',
]
SALVAGE_TEXT: list[str] = [
    '{count: "3", name: "alpha", active: "true", extra: 1}',
    '{"count":4,"name":"beta"}',
    "{count: 5, active: True,}",
    '{"name":"delta","active":false}',
]
ERROR_TEXT: list[str] = [
    '{"count":-1,"name":"alpha","active":true}',
    '{"count":-2,"name":"beta","active":false}',
    '{"count":-3,"name":"gamma","active":true}',
    '{"count":-4,"name":"delta","active":false}',
]


def validator_result(validator: Any, mode: str, value: Any) -> str:
    if mode == "is-valid-mixed":
        return "true" if validator.is_valid(value) else "false"
    try:
        validator.validate(value)
    except ValidationError as exc:
        return "ValidationError: " + exc.message
    return "ok"


def schema_result(schema: Any) -> str:
    try:
        validator_for(schema).check_schema(schema)
    except SchemaError as exc:
        return "SchemaError: " + exc.message
    return "ok"


def repair_result(text: str, salvage: bool) -> Any:
    try:
        result: Any = repair_json(text, return_objects=True, schema=REPAIR_SCHEMA,
                                  schema_repair_mode="salvage" if salvage else "standard")
    except ValueError as exc:
        return "ValueError: " + str(exc)
    return result


def witnesses(results: list[Any]) -> list[str]:
    return [json.dumps(result, separators=(",", ":")) for result in results]


def check(results: list[Any], expected: list[str]) -> None:
    if witnesses(results) != expected:
        raise ValueError("complete schema result or first-error message changed: " + repr(results))


mode = sys.argv[1] if len(sys.argv) > 1 else "validate-valid"
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 100
batches = int(sys.argv[3]) if len(sys.argv) > 3 else 1
warmups = int(sys.argv[4]) if len(sys.argv) > 4 else 0
if rounds < 0 or batches < 1 or warmups < 0:
    raise ValueError("rounds/warmups must be nonnegative, batches positive")
if mode not in ("validate-valid", "validate-early", "validate-late", "is-valid-mixed",
                "check-schema", "repair-standard", "repair-salvage", "repair-error"):
    raise ValueError("unknown schema benchmark mode")

validator_for(SCHEMA).check_schema(SCHEMA)
validator: Any = validator_for(SCHEMA)(SCHEMA)
values = VALID
if mode == "validate-early":
    values = EARLY
elif mode == "validate-late":
    values = LATE
elif mode == "is-valid-mixed":
    values = MIXED
texts = REPAIR_TEXT
if mode == "repair-salvage":
    texts = SALVAGE_TEXT
elif mode == "repair-error":
    texts = ERROR_TEXT
initial: list[Any] = []
for index in range(4):
    if mode == "check-schema":
        initial.append(schema_result(CHECKED[index]))
    elif mode.startswith("repair-"):
        initial.append(repair_result(texts[index], mode == "repair-salvage"))
    else:
        initial.append(validator_result(validator, mode, values[index]))

# Pin the intended acceptance/error distribution independently of cross-backend
# witness agreement. Complete strings below are compared by the campaign runner.
if mode == "validate-valid" and initial != ["ok", "ok", "ok", "ok"]:
    raise ValueError("valid fixture was rejected")
if mode in ("validate-early", "validate-late"):
    for value in initial:
        if not value.startswith("ValidationError: "):
            raise ValueError("invalid fixture was accepted")
if mode == "is-valid-mixed" and initial != ["true", "false", "true", "false"]:
    raise ValueError("is_valid fixture outcome changed")
if mode == "check-schema":
    if initial[:2] != ["ok", "ok"] or not initial[2].startswith("SchemaError: ") or not initial[3].startswith("SchemaError: "):
        raise ValueError("metaschema fixture outcome changed")
if mode in ("repair-standard", "repair-salvage"):
    for value in initial:
        if not isinstance(value, dict):
            raise ValueError("repair fixture was rejected")
if mode == "repair-error":
    for value in initial:
        if not isinstance(value, str) or not value.startswith("ValueError: "):
            raise ValueError("invalid repair fixture was accepted")

expected = witnesses(initial)
print("outputs", repr(expected))
print("witness before", mode, 4, "exact")
print("rounds", rounds)
per_round = sum(len(value) for value in initial)
results = initial.copy()
for batch in range(warmups + batches):
    checksum = 0
    start = perf_counter()
    for _ in range(rounds):
        for index in range(4):
            if mode == "check-schema":
                result: Any = schema_result(CHECKED[index])
            elif mode.startswith("repair-"):
                result = repair_result(texts[index], mode == "repair-salvage")
            else:
                result = validator_result(validator, mode, values[index])
            results[index] = result
            checksum += len(result)
    elapsed = perf_counter() - start
    if checksum != rounds * per_round:
        raise ValueError("schema iteration checksum changed")
    check(results, expected)
    print("witness after", batch, mode, 4, checksum, "exact")
    print("warmup_seconds" if batch < warmups else "seconds", elapsed)
