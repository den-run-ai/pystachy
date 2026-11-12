# pystachy: dynamic-any
# Schema-guided repair of the json_repair port, against upstream's recorded outcomes: each line of
# stdin is a case that tools/json_repair_fuzz.py --record wrote, with what pristine json_repair
# 0.64.9 and jsonschema 4.26 returned or raised for it (values tagged by type, strings as code
# points, as tests/upstream/json_repair/replay.py tags them). The port validates with its own
# validator (ports/json_repair/_jsonschema), natively and under CPython. Then what that validator
# leaves out, which must fail and not pass: references it does not resolve, and draft 3.
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


def outcome(api: str, text: str, flags: Any) -> Any:
    row: dict[str, Any] = {}
    try:
        result: Any = None
        if api == "loads":
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
        row["value"] = tagged(result)
    except Exception as exc:
        row["error"] = type(exc).__name__
        row["message"] = str(exc)
    return row


def recorded() -> None:
    cases = 0
    raised = 0
    different = 0
    for line in sys.stdin:
        case: Any = json.loads(line)
        got = outcome(case["api"], case["input"], case["flags"])
        cases += 1
        if "error" in case["expected"]:
            raised += 1
        if got != case["expected"]:
            different += 1
            print("case", case["id"], json.dumps(case["flags"]), case["input"])
            print("  upstream:", json.dumps(case["expected"]))
            print("  the port:", json.dumps(got))
    print(cases, "recorded cases, of which upstream raises in", raised, "and the port differs in", different)


def left_out() -> None:
    nested: Any = {"type": "object", "properties": {"a": {"anyOf": [{"$ref": "#name"}, {"$ref": "other.json"}]}},
                   "$defs": {"named": {"$anchor": "name", "type": "integer"}}}
    inside: Any = {"type": "object", "properties": {"a": {"$id": "https://example.com/a", "$defs": {"n": {"type": "integer"}},
                                                         "anyOf": [{"$ref": "#/$defs/n"}]}}}
    remote: Any = {"type": "object", "properties": {"a": {"not": {"$ref": "https://example.com/schema.json"}}}}
    draft3: Any = {"$schema": "http://json-schema.org/draft-03/schema#", "type": "object"}
    for name, schema in (("anchor", nested), ("own $id", inside), ("remote", remote), ("draft 3", draft3)):
        print(name, json.dumps(outcome("loads", '{"a": 1}', {"schema": schema})))
    # (not a reference: the root's own $id, and a pointer through an escaped name)
    own: Any = {"$id": "https://example.com/root", "$defs": {"a/b": {"type": "integer"}, "c d": {"type": "string"}},
                "type": "object", "properties": {"a": {"anyOf": [{"$ref": "https://example.com/root#/$defs/a~1b"}]},
                                                 "b": {"anyOf": [{"$ref": "#/$defs/c%20d"}]}}}
    print("own", json.dumps(outcome("loads", '{"a": 1, "b": "x"}', {"schema": own})))
    print("own", json.dumps(outcome("loads", '{"a": "x", "b": 2}', {"schema": own})))


recorded()
left_out()
