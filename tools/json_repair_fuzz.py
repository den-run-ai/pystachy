"""Differential fuzz of the json_repair port against pristine upstream.

Generates deterministic malformed inputs, replays them with tests/upstream/json_repair/replay.py
through pristine upstream under CPython (the oracle), the port under CPython and the port's native
build, and compares typed values, serialized text, repair logs and error messages exactly.

Input families: "mixed" mutates recorded corpus inputs and rendered random values; "long" places
quotes, escapes and structural characters at the string scanner's 64-code-point chunk boundaries;
"number" builds numeric tokens; "comment" places terminators at the comment scanner's windows;
"schema" repairs values that nearly fit a generated JSON Schema, in both schema repair modes.

The schema family needs jsonschema in the CPython that runs this tool: upstream validates with
it, the port with its own validator. Upstream iterates two sets of names, an object's additional
properties (jsonschema) and a schema's required names (json_repair), in an order that the hash
seed decides, and with it which error comes first and the order of salvaged properties. The
family's oracle pins both to the order of the instance and of the schema, which is the port's.

The result is evidence for the generated inputs, not proof of parity. Exit status 1: a difference.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile

from json_repair_parity import exact_equal, normalize

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "tests/upstream/json_repair/replay.py"
MANIFEST = ROOT / "tests/upstream/json_repair/manifest.json"
CASES = ROOT / "tests/upstream/json_repair/cases.json"
FAMILIES = ("mixed", "long", "number", "comment", "schema")
CHUNKS = (64, 128, 192, 256, 320, 384)  # ends of the string scanner's chunks
WINDOWS = (64, 192, 448, 960)  # ends of the comment scanner's doubling windows
TOKENS = list('{}[](),:"\'`#/*\\ \n\t\r') + list("abntrufse019-+.eE_x") + [
    "\u201c", "\u201d", "\u2018", "\u2019", "true", "false", "null", "None", "True", "False", "NaN", "Infinity",
    "-Infinity", "undefined", "//", "/*", "*/", "```", "```json\n", "\n```", "\\n", "\\t", '\\"', "\\\\", "\\/",
    "\\u00e9", "\\ud83d\\ude00", "\\ud83d", "\\x41", "\\'", "\u00e9", "\u65e5\u672c", "\U0001f600", "...", "1e5",
    "-0", "0.5", "1.", ".5", "1_000", "0x1f", "12345678901234567890123", "1/2", "1-2", "1,", '":', '",', '"}',
    '"]', '""', "''", ': "', ', "', "{}", "[]", "\u00a0", "\ufeff", "\u2028", "\x00", "\x0b", "\x0c", "\x1f",
    "key", "value", " and ", "# c\n", "// c\n", "/* c */", "<!-- c -->", "\u2026", "\u0660\u0663", "\u00b2",
    "\u2167", "Here is the JSON: ", " Hope this helps!", '"a": 1', "'a': 'b'", "a: b", '"\\', "\\u12"]
SPECIAL = ['"', "'", "\u201c", "\u201d", "`", "\\", "\\n", "\\t", '\\"', "\\\\", "\\u00e9", "\\ud83d\\ude00", "\n",
           "\t", " ", ",", ":", "{", "}", "[", "]", "/", "//", "/*", "*/", "#", "\u00e9", "\U0001f600", "\\x",
           "\\u12", "\r\n", '",', '":', '" ', '",\n"', '": "', '"}', '"]', "\\'", "\u00a0", "\x00", "\\b\\f\\r",
           "\\n\\n\\t\\r\\b"]
ENDS = ["\n", "\r", "]", "}", ":", "*/", "*", "/", "/*", "//", "#", '"', ",", "\r\n", "*/ ", "-->"]
WORDS = ["lorem", "ipsum", "dolor", "sit", "amet", "x", "\u65e5\u672c\u8a9e", "na\u00efve", "data", "42", "true",
         "a_b", "-"]
TEXTS = ["a", "key", "na\u00efve", "\u65e5\u672c\u8a9e", "x y", "it's", 'say "hi"', "a,b", "a:b", "{x}", "[1]",
         "line\nbreak", "tab\t", "back\\slash", "\U0001f600", "", " ", "true", "12", "// no", "/* no */", "# no"]
# Every API and option that the replay program passes on.
FLAGS = [("repair_json", {"return_objects": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True, "logging": True}),
         ("repair_json", {"return_objects": True, "strict": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True, "strict": True}),
         ("repair_json", {"return_objects": True, "stream_stable": True}),
         ("repair_json", {"return_objects": True, "skip_json_loads": True, "stream_stable": True}),
         ("repair_json", {"return_objects": False, "ensure_ascii": False}),
         ("repair_json", {"return_objects": False, "skip_json_loads": True}),
         ("loads", {}),
         ("loads", {"logging": True})]


SCHEMA_FLAGS = [("repair_json", {"return_objects": True}),
                ("repair_json", {"return_objects": True, "skip_json_loads": True}),
                ("repair_json", {"return_objects": True, "logging": True}),
                ("repair_json", {"return_objects": True, "skip_json_loads": True, "logging": True}),
                ("repair_json", {"return_objects": False}),
                ("repair_json", {"return_objects": False, "ensure_ascii": False}),
                ("repair_json", {"return_objects": True, "stream_stable": True}),
                ("repair_json", {"return_objects": True, "strict": True}),
                ("loads", {}),
                ("loads", {"skip_json_loads": True}),
                ("loads", {"logging": True}),
                ("loads", {"skip_json_loads": True, "logging": True})]
NAMES = ["a", "b", "name", "id", "tags", "x-1", "user id", "n\u00e9"]
SCALARS = ["string", "integer", "number", "boolean", "null"]
PATTERNS = ["^a", "id$", "^x-", "a", "^name$", "[0-9]+", "^(a|b)$", "\\d", "^\u00e9"]
DIALECTS = ["http://json-schema.org/draft-07/schema#", "http://json-schema.org/draft-06/schema#",
            "http://json-schema.org/draft-04/schema#", "https://json-schema.org/draft/2019-09/schema",
            "https://json-schema.org/draft/2020-12/schema", "https://example.com/no-such-dialect"]
# The pins of the schema family's oracle (see the module's description).
PINNED = """import runpy
import sys

import jsonschema._keywords
import json_repair.parser_schema


def ordered(names=()):
    return list(dict.fromkeys(names))


jsonschema._keywords.set = ordered
json_repair.parser_schema.set = ordered
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


PERSON = {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"},
                                           "tags": {"type": "array", "items": {"type": "string"}},
                                           "active": {"type": "boolean", "default": True}},
          "required": ["name", "age"]}
TREE = {"$defs": {"node": {"type": "object", "properties": {"value": {"type": "number"},
                                                            "children": {"type": "array",
                                                                         "items": {"$ref": "#/$defs/node"}}},
                           "required": ["value"], "additionalProperties": False}},
        "$ref": "#/$defs/node"}
# What schema-guided repair is documented and tested to do, each text under every mode it is given:
# (text, schema, modes).
EXAMPLES = [
    ('{name: "Ann", age: "42", tags: "x"}', PERSON, ("standard", "salvage")),
    ('{"name": "Ann", "age": 41.0, "extra": 1, "tags": [1, 2.5]}', PERSON, ("standard",)),
    ('{"name": "Ann"}', PERSON, ("standard", "salvage")),
    ('["Ann", 42, ["a"], "yes"]', PERSON, ("standard", "salvage")),
    ('[{"name": "Ann", "age": 1}]', PERSON, ("standard", "salvage")),
    ('"{\\"name\\": \\"Ann\\", \\"age\\": 3}"', PERSON, ("standard", "salvage")),
    ('{"name": "Ann", "age": "x"}', PERSON, ("standard", "salvage")),
    ('{"name": 7, "age": "7", "active": "no"', PERSON, ("standard",)),
    ('{"value": "1.5", "children": [{"value": 2, "x": 1}, {"children": []}]}', TREE, ("standard", "salvage")),
    ('{"value": 1, "children": {"value": 2}}', TREE, ("standard",)),
    ('{"a": "1", "b": 2}', {"type": "object", "properties": {"a": {"type": "integer"}}, "additionalProperties": False},
     ("standard",)),
    ('{"a": 1, "b_id": "2", "c": 3}', {"type": "object", "patternProperties": {"_id$": {"type": "integer"},
                                                                              "^[0-9]+$": {"type": "string"}},
                                       "additionalProperties": False}, ("standard",)),
    ('{"k": "v", "n": "3"}', {"type": "object", "additionalProperties": {"type": ["integer", "string"]}}, ("standard",)),
    ('[1, "2", 3.0, "x"]', {"type": "array", "items": {"type": "integer"}}, ("standard", "salvage")),
    ('["1", "b", 3]', {"type": "array", "prefixItems": [{"type": "integer"}, {"type": "string"}], "items": False},
     ("standard",)),
    ('["1", "b", 3]', {"type": "array", "items": [{"type": "integer"}, {"type": "string"}], "additionalItems": False},
     ("standard",)),
    ('["1", "b", "3"]', {"$schema": "http://json-schema.org/draft-07/schema#", "type": "array",
                         "items": [{"type": "integer"}], "additionalItems": {"type": "integer"}}, ("standard",)),
    ('[]', {"type": "array", "items": {"type": "integer"}, "minItems": 1}, ("standard", "salvage")),
    ('3', {"type": "array", "items": {"type": "integer"}}, ("standard",)),
    ('{"mode": "FAST"}', {"type": "object", "properties": {"mode": {"enum": ["fast", "slow"]}}}, ("standard",)),
    ('{"mode": "fast"}', {"type": "object", "properties": {"mode": {"const": "slow"}}}, ("standard",)),
    ('{}', {"type": "object", "properties": {"mode": {"enum": ["fast", "slow"]}, "n": {"const": 3},
                                            "s": {"type": "string"}, "l": {"type": "array"}},
           "required": ["mode", "n", "s", "l"]}, ("standard", "salvage")),
    ('{"v": "12"}', {"type": "object", "properties": {"v": {"anyOf": [{"type": "integer"}, {"type": "string"}]}}},
     ("standard",)),
    ('{"v": "12"}', {"type": "object", "properties": {"v": {"oneOf": [{"type": "integer"}, {"type": "number"}]}}},
     ("standard",)),
    ('{"v": 12.5}', {"type": "object", "properties": {"v": {"allOf": [{"type": "number"}, {"maximum": 10}]}}},
     ("standard",)),
    ('{"v": null}', {"type": "object", "properties": {"v": {"type": ["string", "null"]}}}, ("standard",)),
    ('{"v": "abc"}', {"type": "object", "properties": {"v": {"type": "string", "pattern": "^[0-9]+$"}}}, ("standard",)),
    ('{"v": "abc"}', {"type": "object", "properties": {"v": {"type": "string", "maxLength": 2}}}, ("standard",)),
    ('{"v": 7}', {"type": "object", "properties": {"v": {"type": "integer", "multipleOf": 2}}}, ("standard",)),
    ('{"v": [1, 1]}', {"type": "object", "properties": {"v": {"type": "array", "uniqueItems": True}}}, ("standard",)),
    ('{"a": 1}', {"type": "object", "dependentRequired": {"a": ["b"]}}, ("standard",)),
    ('{"a": 1, "b": 2}', {"type": "object", "properties": {"a": {}}, "unevaluatedProperties": False}, ("standard",)),
    ('{"a": 1}', {"if": {"required": ["a"]}, "then": {"required": ["b"]}, "else": {"required": ["c"]}}, ("standard",)),
    ('{"a": 1}', {"not": {"required": ["a"]}}, ("standard",)),
    ('{"a": 1}', {"$ref": "#/$defs/missing"}, ("standard",)),
    ('{"a": {"b": 1}}', {"type": "object", "properties": {"a": {"anyOf": [{"$ref": "#/$defs/missing"}]}}},
     ("standard",)),
    ('{"a": 1}', {"$ref": "other.json#/a"}, ("standard",)),
    ('{"a": 1}', {"$ref": 3}, ("standard",)),
    ('{"a": 1}', {"type": "objekt"}, ("standard",)),
    ('{"a": 1}', {"properties": {"a": {"type": "string", "pattern": "("}}}, ("standard",)),
    ('{"a": 1}', {"required": "a"}, ("standard",)),
    ('{"a": 1}', {"type": "object", "properties": {"a": {"minimum": "1"}}}, ("standard",)),
    ('{"a": 1}', True, ("standard", "salvage")),
    ('{"a": 1}', False, ("standard",)),
    ('{"a": 1', {}, ("standard",)),
    ('{"a": "1", "b": [true, "no"]}', {"type": "object", "properties": {"a": {"type": "number"},
                                                                     "b": {"type": "array",
                                                                           "items": {"type": "boolean"}}}},
     ("standard",)),
    ('{"n": 1e400, "big": 123456789012345678901234567890, "f": "1e3"}',
     {"type": "object", "properties": {"n": {"type": "number"}, "big": {"type": "integer"}, "f": {"type": "integer"}}},
     ("standard",)),
    ('{"n\u00e9": "\u00e9t\u00e9", "x": "\\ud83d\\ude00"}', {"type": "object", "properties": {"n\u00e9": {"type": "string", "minLength": 4}}},
     ("standard",)),
]


def scalar_schema(rng, kind):
    schema = {"type": kind}
    extra = rng.randrange(9)
    if kind == "string":
        if extra == 0:
            schema["enum"] = rng.sample(TEXTS, rng.randrange(1, 4))
        elif extra == 1:
            schema["minLength"] = rng.randrange(0, 4)
        elif extra == 2:
            schema["maxLength"] = rng.randrange(0, 6)
        elif extra == 3:
            schema["pattern"] = rng.choice(PATTERNS)
        elif extra == 4:
            schema["const"] = rng.choice(TEXTS)
        elif extra == 5:
            schema["format"] = rng.choice(["date", "email", "regex", "uuid"])
    elif kind in ("integer", "number"):
        if extra == 0:
            schema["minimum"] = rng.choice([0, 1, -5, 2.5])
        elif extra == 1:
            schema["maximum"] = rng.choice([0, 10, 100, 2.5])
        elif extra == 2:
            schema["exclusiveMinimum"] = rng.choice([0, 1])
        elif extra == 3:
            schema["multipleOf"] = rng.choice([1, 2, 5, 0.5, 0.1])
        elif extra == 4:
            schema["enum"] = rng.sample([0, 1, 2, 3, 1.5, 10, True], rng.randrange(1, 4))
        elif extra == 5:
            schema["exclusiveMaximum"] = rng.choice([10, 100])
    elif kind == "boolean" and extra == 0:
        schema["const"] = rng.choice([True, False])
    if rng.randrange(6) == 0:
        schema["default"] = random_value(rng, 0)
    return schema


def random_schema(rng, depth, defs):
    """A schema as a tool or a model declares one: mostly objects of typed properties, with unions,
    references into $defs, defaults and constraints, and now and then a keyword that upstream's
    repair ignores and only validation reads."""
    pick = rng.randrange(20 if depth > 0 else 9)
    if pick < 6:
        return scalar_schema(rng, rng.choice(SCALARS))
    if pick == 6:
        return rng.choice([True, True, False, {}])
    if pick == 7 and defs:
        return {"$ref": "#/$defs/" + rng.choice(sorted(defs))} if rng.randrange(8) else {"$ref": "#/$defs/missing"}
    if pick == 8:
        return {"type": rng.sample(SCALARS + ["array", "object"], rng.randrange(1, 4))}
    if pick < 12:
        schema = {"type": "array"}
        shape = rng.randrange(6)
        if shape < 4:
            schema["items"] = random_schema(rng, depth - 1, defs)
        elif shape == 4:
            schema["prefixItems"] = [random_schema(rng, depth - 1, defs) for _ in range(rng.randrange(1, 3))]
            if rng.randrange(2):
                schema["items"] = rng.choice([False, True, {"type": "string"}])
        else:
            schema["items"] = [random_schema(rng, depth - 1, defs) for _ in range(rng.randrange(1, 3))]
            if rng.randrange(2):
                schema["additionalItems"] = rng.choice([False, True, {"type": "integer"}])
        for keyword, values in (("minItems", [0, 1, 2]), ("maxItems", [0, 1, 3]), ("uniqueItems", [True]),
                                ("contains", [{"type": "integer"}, {"const": "a"}])):
            if rng.randrange(7) == 0:
                schema[keyword] = rng.choice(values)
        if rng.randrange(3) == 0:
            del schema["type"]
        return schema
    if pick < 17:
        names = rng.sample(NAMES, rng.randrange(1, 5))
        schema = {"type": "object", "properties": {name: random_schema(rng, depth - 1, defs) for name in names}}
        if rng.randrange(3):
            schema["required"] = rng.sample(names, rng.randrange(0, len(names) + 1))
        extra = rng.randrange(8)
        if extra == 0:
            schema["additionalProperties"] = False
        elif extra == 1:
            schema["additionalProperties"] = random_schema(rng, depth - 1, defs)
        elif extra == 2:
            schema["patternProperties"] = {rng.choice(PATTERNS): random_schema(rng, depth - 1, defs)}
            if rng.randrange(2):
                schema["additionalProperties"] = False
        elif extra == 3:
            schema[rng.choice(["minProperties", "maxProperties"])] = rng.randrange(0, 3)
        elif extra == 4:
            schema["propertyNames"] = {"pattern": rng.choice(PATTERNS)}
        elif extra == 5:
            schema["dependentRequired"] = {names[0]: rng.sample(NAMES, rng.randrange(1, 3))}
        elif extra == 6:
            schema["unevaluatedProperties"] = rng.choice([False, {"type": "string"}])
        if rng.randrange(5) == 0:
            del schema["type"]
        return schema
    if pick < 19:
        keyword = rng.choice(["anyOf", "oneOf", "allOf"])
        return {keyword: [random_schema(rng, depth - 1, defs) for _ in range(rng.randrange(1, 4))]}
    keyword = rng.choice(["not", "if"])
    schema = {keyword: random_schema(rng, depth - 1, defs)}
    if keyword == "if":
        schema[rng.choice(["then", "else"])] = random_schema(rng, depth - 1, defs)
    return schema


def fitting(rng, schema, root, depth):
    """A value that fits the schema, more or less: what a model that read the schema would write."""
    if not isinstance(schema, dict) or depth > 6:
        return random_value(rng, 1)
    if isinstance(schema.get("$ref"), str):
        target = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            target = target.get(part) if isinstance(target, dict) else None
        return fitting(rng, target, root, depth + 1)
    for keyword in ("anyOf", "oneOf", "allOf"):
        if isinstance(schema.get(keyword), list) and schema[keyword]:
            return fitting(rng, rng.choice(schema[keyword]), root, depth + 1)
    if "const" in schema and rng.randrange(4):
        return schema["const"]
    if isinstance(schema.get("enum"), list) and schema["enum"] and rng.randrange(4):
        return rng.choice(schema["enum"])
    kind = schema.get("type")
    if isinstance(kind, list) and kind:
        kind = rng.choice(kind)
    if kind is None:
        kind = "object" if "properties" in schema else "array" if "items" in schema or "prefixItems" in schema else None
    if kind == "object":
        value = {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        for name, each in properties.items():
            if name in required or rng.randrange(6):
                value[name] = fitting(rng, each, root, depth + 1)
        if rng.randrange(4) == 0:
            value[rng.choice(NAMES + ["extra", "x-9", "aid"])] = random_value(rng, 1)
        return value
    if kind == "array":
        items = schema.get("prefixItems", schema.get("items"))
        if isinstance(items, list):
            return [fitting(rng, each, root, depth + 1) for each in items] + [random_value(rng, 0)] * rng.randrange(2)
        return [fitting(rng, items, root, depth + 1) for _ in range(rng.randrange(4))]
    if kind == "string":
        return rng.choice(TEXTS + ["a1", "x-1", "id", "name"])
    if kind == "integer":
        return rng.choice([0, 1, 2, 3, 7, 10, 42, -5, 100])
    if kind == "number":
        return rng.choice([0, 1.5, 2.5, 10, -0.5, 3.0, 1e20])
    if kind == "boolean":
        return rng.choice([True, False])
    if kind == "null":
        return None
    return random_value(rng, 1)


def misfit(rng, value, depth=0):
    """The value with the misfits that schema repair mends or rejects: numbers as text and text
    as numbers, yes for true, a lone item for an array, a container as its JSON text, a missing
    or misplaced property, an array for an object."""
    change = rng.randrange(16 if depth == 0 else 26)
    if isinstance(value, dict):
        out = {key: misfit(rng, item, depth + 1) for key, item in value.items()}
        if change == 0 and out:
            del out[rng.choice(sorted(out))]
        elif change == 1:
            return json.dumps(out)
        elif change == 2:
            return list(out.values())
        elif change == 3:
            return [out]
        return out
    if isinstance(value, list):
        out = [misfit(rng, item, depth + 1) for item in value]
        if change == 0 and out:
            return out[0]
        if change == 1:
            return json.dumps(out)
        if change == 2:
            return out + [rng.choice([None, "x", 1])]
        return out
    if change > 4:
        return value
    if isinstance(value, bool):
        return rng.choice(["true", "yes", "No", "on", 1, 0, "0", "off", 1.0])
    if isinstance(value, (int, float)):
        return rng.choice([str(value), float(value), str(value) + ".0", [value], " " + str(value), "1e2"])
    if isinstance(value, str):
        return rng.choice([[value], 3, 2.5, None, True, value.upper()])
    return rng.choice(["null", "", 0, []])


def schema_case(rng, seeds):
    """A text and the schema options to repair it with."""
    defs = {}
    if rng.randrange(3) == 0:
        for name in rng.sample(["a", "item", "node"], rng.randrange(1, 3)):
            defs[name] = random_schema(rng, 2, {})
    schema = random_schema(rng, rng.randrange(1, 4), defs)
    while rng.randrange(8) and not (isinstance(schema, dict) and {"properties", "items", "prefixItems", "anyOf", "oneOf",
                                                                 "allOf"} & set(schema)):
        # mostly an object or an array at the root, as a tool's arguments and a model's reply are
        schema = random_schema(rng, rng.randrange(1, 4), defs)
    if isinstance(schema, dict):
        if defs:
            schema["$defs"] = defs
            if rng.randrange(6) == 0:
                defs[rng.choice(sorted(defs))] = {"$ref": "#"}
        if rng.randrange(8) == 0:
            schema = {"$schema": rng.choice(DIALECTS), **schema}
        if rng.randrange(25) == 0:
            # what no metaschema allows: an invalid schema, which upstream reports before any repair
            schema[rng.choice(["type", "required", "properties", "minItems", "pattern", "items", "enum"])] = rng.choice(
                ["strin", 3, -1, "[", [1], None, {"a": 1}])
    value = fitting(rng, schema, schema, 0)
    pick = rng.randrange(10)
    if pick < 5:
        value = misfit(rng, value)
    elif pick == 5:
        value = random_value(rng, 2)
    text = rendered(rng, value) if rng.randrange(4) else json.dumps(value)
    if rng.randrange(3) == 0:
        text = mutated(rng, text, seeds)
    options = {"schema": schema}
    mode = rng.randrange(20)
    if mode < 7:
        options["schema_repair_mode"] = "salvage"
    elif mode == 7:
        options["schema_repair_mode"] = "standard"
    elif mode == 8:
        options["schema_repair_mode"] = "quick"
    return text, options


def filler(rng, length):
    chars = []
    while len(chars) < length:
        chars.extend(rng.choice(WORDS))
        if rng.randrange(3):
            chars.append(" ")
    return chars[:length]


def spliced(rng, chars, marks, pieces, lead=0):
    """chars with up to four pieces put at, or within three characters of, one of the marks."""
    for _ in range(rng.randrange(5)):
        at = rng.choice(marks) + rng.randrange(-3, 4) - lead if rng.randrange(3) else rng.randrange(len(chars) + 1)
        at = min(max(at, 0), len(chars))
        chars[at:at + rng.randrange(2)] = list(rng.choice(pieces))
    return "".join(chars)


def random_value(rng, depth):
    kind = rng.randrange(9 if depth > 0 else 6)
    if kind == 0:
        return rng.choice([True, False, None])
    if kind == 1:
        return rng.randrange(-5, 2000)
    if kind == 2:
        return rng.choice([0.5, -1.25, 1e20, 3.0, 1e-7, 123456789012345678])
    if kind < 6:
        return rng.choice(TEXTS) + (rng.choice(TEXTS) if rng.randrange(4) == 0 else "")
    if kind < 8:
        return {rng.choice(TEXTS) if rng.randrange(5) else "k%d" % i: random_value(rng, depth - 1)
                for i in range(rng.randrange(4))}
    return [random_value(rng, depth - 1) for _ in range(rng.randrange(5))]


def rendered(rng, value):
    style = rng.randrange(6)
    if style == 0:
        return json.dumps(value)
    if style == 1:
        return json.dumps(value, ensure_ascii=False, indent=rng.choice([1, 2, "\t"]))
    if style == 2:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if style == 3:
        return repr(value)
    if style == 4:
        return json.dumps(value, ensure_ascii=False).replace('"', rng.choice(["'", "\u201c", "", "`"]))
    return json.dumps(value, ensure_ascii=False).replace(",", rng.choice([", ", " ", ",,", ";", "\n"]))


def mutated(rng, text, seeds):
    for _ in range(rng.choice([0, 1, 1, 1, 2, 2, 3, 4, 6])):
        operation = rng.randrange(10)
        at = rng.randrange(len(text) + 1)
        if operation == 0:
            text = text[:at] + text[at + rng.randrange(1, 4):]
        elif operation < 4:
            text = text[:at] + rng.choice(TOKENS) + text[at:]
        elif operation == 4:
            text = text[:at] + rng.choice(TOKENS) + text[at + 1:]
        elif operation == 5:
            end = min(len(text), at + rng.randrange(1, 8))
            text = text[:end] + text[at:end] + text[end:]
        elif operation == 6:
            text = text[:at]
        elif operation == 7:
            other = rng.choice(seeds)
            text += rng.choice(["", " ", "\n", ",", " and ", "```"]) + other[:rng.randrange(len(other) + 1)]
        elif operation == 8:
            text = (rng.choice(["", "Sure: ", "```json\n", "```\n", "json ", "Result = ", "// x\n", "\ufeff"]) + text +
                    rng.choice(["", "\n```", " done.", ";", "\n", " // end", " /* end"]))
        else:
            other = rng.randrange(len(text) + 1)
            text = text[:min(at, other)] + text[max(at, other):]
    return text


def mixed_text(rng, seeds):
    pick = rng.randrange(10)
    if pick < 4:
        text = rng.choice(seeds)
    elif pick < 9:
        text = rendered(rng, random_value(rng, rng.randrange(1, 4)))
    else:
        text = "".join(rng.choice(TOKENS) for _ in range(rng.randrange(1, 14)))
    return mutated(rng, text, seeds)


def long_text(rng, seeds):
    def content():
        return spliced(rng, filler(rng, rng.choice(CHUNKS) + rng.randrange(-4, 5)), CHUNKS, SPECIAL)

    quote = rng.choice(['"', '"', '"', "'", "\u201c", "", "`"])
    close = rng.choice(["", '"', "'"]) if rng.randrange(6) == 0 else {"\u201c": "\u201d"}.get(quote, quote)
    parts = [quote + content() + close for _ in range(rng.randrange(1, 4))]
    shape = rng.randrange(8)
    if shape == 0:
        text = parts[0]
    elif shape == 1:
        text = "[" + ", ".join(parts) + rng.choice(["]", "", ",]"])
    elif shape == 2:
        text = '{"k": ' + parts[0] + rng.choice(["}", "", ', "z": 1}', "\n}"])
    elif shape == 3:
        text = "{" + parts[0] + ": " + parts[-1] + rng.choice(["}", ""])
    elif shape == 4:
        text = '{"a": [' + ", ".join(parts) + '], "b": ' + parts[0] + "}"
    elif shape == 5:
        text = rng.choice(["/* ", "// ", "# "]) + content() + rng.choice([" */", "\n", ""]) + '{"k": ' + parts[0] + "}"
    elif shape == 6:
        text = '{"k": ' + parts[0] + " " + rng.choice(["//", "/*", "#"]) + content() + rng.choice(["\n}", "*/}", ""])
    else:
        text = "Text " + content() + ' {"k": ' + parts[0] + "} " + content()
    return mutated(rng, text, seeds) if rng.randrange(3) == 0 else text


def number_text(rng, seeds):
    token = "".join(rng.choice("0123456789012345+-..eE_/, xaAn\u0660\u00b2") for _ in range(rng.randrange(1, 13)))
    if rng.randrange(5) == 0:
        token = (rng.choice(["-", "", "+"]) + rng.choice("123456789") +
                 "".join(rng.choice("0123456789") for _ in range(rng.randrange(15, 45))))
    if rng.randrange(6) == 0:
        token += rng.choice(["e400", "E-400", ".", "e", "e+", "-", "/3", ".0e3", "_000", "n", "L", "%"])
    shape = rng.randrange(9)
    if shape == 0:
        return token
    if shape == 1:
        return "[" + token + rng.choice(["]", "", ",]", " ]"])
    if shape == 2:
        return "[" + token + ", " + token[::-1] + "]"
    if shape == 3:
        return '{"a": ' + token + rng.choice(["}", "", ', "b": 2}', " }", "\n}"])
    if shape == 4:
        return "{" + token + ": " + token + "}"
    if shape == 5:
        return '{"a": [' + token + rng.choice(["]}", "", "]", "}"])
    if shape == 6:
        return token + rng.choice([" ", "\n", ","]) + token
    if shape == 7:
        return '{"a": ' + token + rng.choice([" // c\n}", "/* c */}", " # c", ","])
    return "(" + token + rng.choice([")", "", ", 1)"])


def comment_text(rng, seeds, nested=False):
    opener = rng.choice(["//", "#", "/*", "/*", "/", "<!--"])
    length = rng.choice(WINDOWS) + rng.randrange(-3, 4) if rng.randrange(4) else rng.randrange(40)
    body = spliced(rng, filler(rng, length), WINDOWS, ENDS, len(opener))
    comment = opener + body + rng.choice(["", "", "\n", "*/", "\r", " */ "])
    shape = rng.randrange(9 if nested else 10)
    if shape == 0:
        return comment
    if shape == 1:
        return comment + '{"a": 1}'
    if shape == 2:
        return "[1, " + comment + rng.choice(["2]", "]", "", ", 2]"])
    if shape == 3:
        return '{"a": 1, ' + comment + rng.choice(['"b": 2}', "}", ""])
    if shape == 4:
        return '{"a": ' + comment + rng.choice(["1}", "}", '"x"}', ""])
    if shape == 5:
        return "{" + comment + rng.choice(['"a": 1}', ": 1}", "}", ""])
    if shape == 6:
        return '{"a" ' + comment + rng.choice([": 1}", "1}", "}"])
    if shape == 7:
        return '{"a": 1} ' + comment + rng.choice(["", '{"b": 2}', "[3]"])
    if shape == 8:
        return '{"a": "x' + comment + rng.choice(['"}', "}", ""])
    return "[" + comment + comment_text(rng, seeds, True)[:300] + "]"


GENERATORS = {"mixed": mixed_text, "long": long_text, "number": number_text, "comment": comment_text}


def corpus_seeds(cases):
    return sorted({row["input"] for row in cases if "input_codepoints" not in row and len(row["input"]) <= 240})


def requests(seed, count, family, seeds):
    """count replay requests: each generated text under three API and option combinations. A text
    holds no surrogate code point, which the requests' JSON transport would not preserve."""
    rng = random.Random(f"{family}:{seed}")
    rows = []
    if family == "schema":
        for text, schema, modes in EXAMPLES:
            for mode in modes:
                for api, flags in (SCHEMA_FLAGS[2], SCHEMA_FLAGS[4]):
                    rows.append({"id": len(rows), "api": api, "input": text,
                                 "flags": {**flags, "schema": schema, "schema_repair_mode": mode}})
        rows = rows[:count]
    while len(rows) < count:
        options = {}
        if family == "schema":
            text, options = schema_case(rng, seeds)
        else:
            text = GENERATORS[family](rng, seeds)
        if len(text) > (400 if family in ("mixed", "schema") else 2500) or any(0xD800 <= ord(char) <= 0xDFFF for char in text):
            continue
        for api, flags in rng.sample(SCHEMA_FLAGS if family == "schema" else FLAGS, 3):
            if len(rows) < count:
                rows.append({"id": len(rows), "api": api, "input": text, "flags": {**flags, **options}})
    return rows


def outcome(line, ident):
    """Case ident's row of the replay program's output: a value or an error, never both."""
    if not line:
        raise ValueError(f"no outcome for case {ident}")
    row = json.loads(line)
    if type(row.get("id")) is not int or row.pop("id") != ident:
        raise ValueError(f"expected case {ident}'s outcome, not {line[:80]!r}")
    if ("value" in row) == ("error" in row):
        raise ValueError(f"case {ident} needs exactly one of a value and an error")
    if "value" in row:
        row["value"] = normalize(row["value"])
    return row


def checked(output, count):
    """How many of the output file's rows are errors. It must hold one row for each case, in order."""
    errors = 0
    with open(output) as rows:
        for ident in range(count):
            errors += "error" in outcome(rows.readline(), ident)
        if rows.readline():
            raise ValueError(f"more than {count} outcomes")
    return errors


def differing(oracle, other, count):
    """The ids of the first count cases whose outcomes differ between two output files, of which
    other holds no more, and the oracle's outcomes of the first 25 of them. The files are read a
    row at a time: a long family's outcomes take gigabytes as Python values."""
    bad = []
    kept = {}
    with open(oracle) as first, open(other) as second:
        for ident in range(count):
            expected = outcome(first.readline(), ident)
            if not exact_equal(expected, outcome(second.readline(), ident)):
                bad.append(ident)
                if len(kept) < 25:
                    kept[ident] = expected
        if second.readline():
            raise ValueError(f"more than {count} outcomes")
    return bad, kept


def sample(rows, oracle):
    """Each example's first run in each mode and, of the generated cases under 700 characters, the
    first of each kind of outcome: an error's first words, without what it quotes of the case, or
    a value's type by API and mode. The sample is small because the native test that replays it
    also runs with a collection at every allocation. Each row carries upstream's raw outcome as
    "expected"; the outcomes that jsonschema's reference library words (an unresolvable
    reference) are left out, as the port's wording of some is its own."""
    kept = []
    seen = {}
    examples = sum(2 * len(modes) for _, _, modes in EXAMPLES)
    with open(oracle) as lines:
        for row, line in zip(rows, lines, strict=True):
            expected = json.loads(line)
            if expected.pop("id") != row["id"]:
                raise ValueError(f"expected case {row['id']}'s outcome")
            if "error" in expected:
                if expected["error"] in ("_WrappedReferencingError", "PointerToNowhere", "Unresolvable", "NoSuchAnchor",
                                         "RecursionError"):
                    continue
                words = re.sub(r"'[^']*'|\"[^\"]*\"|\[.*\]|\{.*\}|[-+.0-9e]+|\$\S*", "", expected["message"])
                kind = expected["error"] + ":" + words[:24]
            else:
                kind = f"value:{expected['value'][0]}:{row['api']}:{row['flags'].get('schema_repair_mode')}"
            if row["id"] < examples:
                keep = row["id"] % 2 == 0
            else:
                keep = kind not in seen and len(json.dumps(row)) <= 700
                if keep:
                    seen[kind] = True
            if keep:
                kept.append(dict(row, id=len(kept), expected=expected))
    return kept


def check_upstream(upstream):
    """The oracle's sources must be the pinned release's, by the hashes of the corpus manifest."""
    manifest = json.loads(MANIFEST.read_text())
    for relative, expected in manifest["source_sha256"].items():
        path = upstream / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"{path} is not json_repair {manifest['tag']}'s {relative}")
    return manifest["tag"]


def replayed(label, command, env, inputs, timeout):
    """The file of the replay program's output for the inputs; a failure or any stderr is an error."""
    output = inputs.with_name(inputs.stem + "-" + "".join(char if char.isalnum() else "-" for char in label) + ".out")
    with open(output, "w") as out:
        result = subprocess.run([*command, str(inputs)], env=env, stdout=out, stderr=subprocess.PIPE, text=True,
                                timeout=timeout, cwd=inputs.parent)
    if result.returncode or result.stderr:
        raise ValueError(f"{label}: exit {result.returncode}: {result.stderr[-2000:]}")
    return output


def hosted_env(package_parent):
    """CPython with exactly one json_repair on its path; the replay program's directory has none."""
    env = dict(os.environ, PYTHONPATH=str(package_parent), PYTHONHASHSEED="0")
    result = subprocess.run([sys.executable, "-c", "import json_repair; print(json_repair.__file__)"], env=env,
                            capture_output=True, text=True, cwd=REPLAY.parent)
    found = result.stdout.strip()
    if result.returncode or Path(found).resolve() != (package_parent / "json_repair/__init__.py").resolve():
        raise ValueError(f"CPython imports {found or 'no json_repair'}, not {package_parent}'s")
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upstream", type=Path, required=True, help="pristine checkout of the pinned release")
    parser.add_argument("--compiler", type=Path, default=ROOT / "pystachy", help="built native compiler")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--cases", type=int, default=30000, help="cases of each family")
    parser.add_argument("--family", choices=FAMILIES, action="append", help="default: every family")
    parser.add_argument("--jit", action="store_true", help="also replay through the JIT")
    parser.add_argument("--gc-stress", type=int, default=0, metavar="N",
                        help="also replay each family's first N cases natively with a stressed collector, "
                             "which takes seconds for a case with long output")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds for each replay")
    parser.add_argument("--report", type=Path, help="write counts and the first differing cases as JSON")
    parser.add_argument("--record", type=Path, metavar="FILE",
                        help="write a sample of the schema family's cases with upstream's outcomes, by kind of "
                             "outcome, as the JSON lines that "
                             "tests/programs/apps/port_json_repair_schema.py reads; only where every replay matched")
    args = parser.parse_args(argv)
    tag = check_upstream(args.upstream.resolve())
    compiler = args.compiler.resolve()
    seeds = corpus_seeds(json.loads(CASES.read_text()))
    report = {"upstream": tag, "python": sys.version.split()[0], "seed": args.seed, "families": {}}
    failed = False
    with tempfile.TemporaryDirectory(prefix="pystachy-json-repair-fuzz-") as scratch:
        scratch = Path(scratch)
        native = dict(os.environ, PYSTACHY_PATH=str(ROOT / "ports"))
        executable = scratch / "replay"
        subprocess.run([str(compiler), "build", str(REPLAY), "-o", str(executable)], env=native, check=True,
                       timeout=args.timeout)
        runs = [("port under CPython", [sys.executable, str(REPLAY)], hosted_env(ROOT / "ports")),
                ("native AOT", [str(executable)], native)]
        if args.jit:
            runs.append(("native JIT", [str(compiler), "run", str(REPLAY)], native))
        oracle_env = hosted_env(args.upstream.resolve() / "src")
        pinned = scratch / "pinned.py"
        pinned.write_text(PINNED)
        for family in args.family or FAMILIES:
            rows = requests(args.seed, args.cases, family, seeds)
            inputs = scratch / f"{family}.jsonl"
            inputs.write_text("".join(json.dumps(row) + "\n" for row in rows))
            command = [sys.executable, str(pinned), str(REPLAY)] if family == "schema" else [sys.executable, str(REPLAY)]
            oracle = replayed("upstream", command, oracle_env, inputs, args.timeout)
            entry = {"cases": len(rows), "texts": len({row["input"] for row in rows}),
                     "errors": checked(oracle, len(rows)), "differences": {}}
            report["families"][family] = entry
            checks = [(label, command, env, inputs, len(rows)) for label, command, env in runs]
            if args.gc_stress > 0:
                first = scratch / f"{family}-stress.jsonl"
                first.write_text("".join(json.dumps(row) + "\n" for row in rows[:args.gc_stress]))
                checks.append(("native AOT, stressed collector", [str(executable)], dict(native, PYSTACHY_GC_STRESS="1"),
                               first, min(args.gc_stress, len(rows))))
            for label, command, env, path, count in checks:
                try:
                    output = replayed(label, command, env, path, args.timeout)
                    bad, kept = differing(oracle, output, count)
                    output.unlink()  # (a long family's output is a gigabyte)
                except (ValueError, OSError, subprocess.SubprocessError) as error:
                    # One replay that fails or runs out of time fails the run, and the others' results stay.
                    entry["differences"][label] = {"error": str(error)[:2000]}
                    failed = True
                    print(f"{family}: {label}: no result: {str(error)[:300]}", flush=True)
                    continue
                entry["differences"][label] = [dict(rows[ident], expected=expected) for ident, expected in kept.items()]
                failed = failed or len(bad) > 0
                print(f"{family}: {label}: {count - len(bad)}/{count} match upstream {tag}", flush=True)
                for ident in bad[:5]:
                    print("  " + json.dumps(rows[ident], ensure_ascii=True))
            if args.record and family == "schema" and not failed:
                args.record.write_text("".join(json.dumps(row, ensure_ascii=True) + "\n" for row in sample(rows, oracle)))
            oracle.unlink()
    report["result"] = "fail" if failed else "pass"
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(f"json-repair-fuzz: {error}")
