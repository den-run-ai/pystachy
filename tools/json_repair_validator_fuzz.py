"""Differential fuzz of the json_repair port's JSON Schema validator against jsonschema.

Generates deterministic schemas, valid and invalid, over the keywords of drafts 4 to 2020-12, and
instances for them. For each schema it compares what check_schema() raises, and for each instance
of a valid schema what validate() raises and is_valid() returns: the error's class and message.
Run it with a CPython that has jsonschema 4.26 installed; the port's validator needs nothing.

Two kinds of difference are counted and not failures. jsonschema tries an object's additional
properties in the order of a set of their names, which the hash seed decides; it is pinned here
to the order of the instance, the port's. And the port resolves only "#" and "#/..." references
into the root schema: where it raises its unresolvable-reference error for an anchor, another
document or a reference inside a subschema with its own $id, jsonschema's outcome is its own.

The result is evidence for the generated cases, not proof. Exit status 1: a difference.

--answers FILE instead records jsonschema's outcomes for the hand-written PAIRS and CHECKED
schemas below, which tools/test_json_repair_validator.py holds the port's validator to where no
jsonschema is installed.
"""
import argparse
import json
from pathlib import Path
import random
import sys
import warnings

ROOT = Path(__file__).resolve().parent.parent
ANSWERS = ROOT / "tests/upstream/json_repair/validator_answers.json"
D7 = "http://json-schema.org/draft-07/schema#"
D4 = "http://json-schema.org/draft-04/schema#"
D19 = "https://json-schema.org/draft/2019-09/schema"
# Each keyword's errors, by hand: what --answers records of jsonschema for tools/test_json_repair_validator.py.
PAIRS = [
    ({"type": "integer"}, "a"), ({"type": ["string", "null"]}, 3), ({"type": "integer"}, 3.0), ({"type": "integer"}, True),
    ({"$schema": D4, "type": "integer"}, 3.0), ({"type": "number"}, False),
    ({"required": ["a", "b"]}, {"b": 1}), ({"properties": {"a": {"type": "string"}}}, {"a": 1}),
    ({"additionalProperties": False}, {"b": 1, "a": 2}), ({"additionalProperties": False, "patternProperties": {"^x": {}}}, {"b": 1}),
    ({"additionalProperties": {"type": "integer"}}, {"a": "x"}), ({"patternProperties": {"^a": {"type": "integer"}}}, {"ab": "x"}),
    ({"propertyNames": {"maxLength": 1}}, {"ab": 1}), ({"minProperties": 1}, {}), ({"minProperties": 2}, {"a": 1}),
    ({"maxProperties": 0}, {"a": 1}), ({"maxProperties": 1}, {"a": 1, "b": 2}),
    ({"dependentRequired": {"a": ["b"]}}, {"a": 1}), ({"dependentSchemas": {"a": {"required": ["c"]}}}, {"a": 1}),
    ({"$schema": D7, "dependencies": {"a": ["b"], "c": {"minProperties": 3}}}, {"a": 1, "c": 2}),
    ({"items": {"type": "integer"}}, [1, "a"]), ({"prefixItems": [{"type": "integer"}], "items": False}, [1, 2, 3]),
    ({"prefixItems": [{"type": "integer"}, {}], "items": False}, [1, 2, 3]),
    ({"$schema": D7, "items": [{"type": "integer"}], "additionalItems": False}, [1, "a", "b"]),
    ({"$schema": D7, "items": [{"type": "integer"}], "additionalItems": {"type": "string"}}, [1, 2]),
    ({"minItems": 1}, []), ({"minItems": 2}, [1]), ({"maxItems": 0}, [1]), ({"maxItems": 1}, [1, 2]),
    ({"uniqueItems": True}, [1, 1.0]), ({"uniqueItems": True}, [1, True]), ({"uniqueItems": True}, [{"a": [1]}, {"a": [1]}]),
    ({"contains": {"type": "integer"}}, ["a"]), ({"contains": {"type": "integer"}, "minContains": 2}, [1, "a"]),
    ({"contains": {"type": "integer"}, "maxContains": 1}, [1, 2]), ({"$schema": D7, "contains": {"type": "integer"}}, ["a"]),
    ({"enum": [1, "a", None]}, True), ({"enum": [[1], {"a": 1}]}, [True]), ({"const": {"a": [1.0]}}, {"a": [1]}), ({"const": 1}, True),
    ({"minimum": 3}, 2.5), ({"maximum": 3}, 4), ({"exclusiveMinimum": 3}, 3), ({"exclusiveMaximum": 3.5}, 3.5),
    ({"$schema": D4, "minimum": 3, "exclusiveMinimum": True}, 3), ({"$schema": D4, "maximum": 3, "exclusiveMaximum": True}, 3),
    ({"multipleOf": 2}, 7), ({"multipleOf": 0.1}, 0.25), ({"multipleOf": 0.5}, 1e308), ({"multipleOf": 3}, 7.5),
    ({"minLength": 1}, ""), ({"minLength": 3}, "é"), ({"maxLength": 0}, "a"), ({"maxLength": 1}, "\U0001f600a"),
    ({"pattern": "^a+$"}, "ab"), ({"format": "regex"}, "("),
    ({"allOf": [{"type": "integer"}, {"minimum": 3}]}, 2), ({"anyOf": [{"type": "integer"}, {"type": "null"}]}, "a"),
    ({"oneOf": [{"type": "integer"}, {"minimum": 3}]}, 5), ({"oneOf": [{"type": "integer"}, {"type": "null"}]}, "a"),
    ({"not": {"type": "integer"}}, 3), ({"if": {"type": "integer"}, "then": {"minimum": 3}, "else": {"type": "null"}}, 2),
    ({"if": {"type": "integer"}, "then": {"minimum": 3}, "else": {"type": "null"}}, "a"),
    ({"$defs": {"n": {"type": "integer"}}, "$ref": "#/$defs/n"}, "a"), ({"$ref": "#/$defs/nope"}, 1), ({"$ref": "#/"}, 1),
    ({"$defs": {"a/b": {"type": "null"}, "c d": False}, "allOf": [{"$ref": "#/$defs/a~1b"}, {"$ref": "#/$defs/c%20d"}]}, None),
    ({"$schema": D7, "$ref": "#/definitions/n", "minimum": 99, "definitions": {"n": {"type": "integer"}}}, 3),
    ({"$ref": "#/$defs/n", "minimum": 99, "$defs": {"n": {"type": "integer"}}}, 3),
    ({"$schema": D19, "$recursiveRef": "#", "type": "array", "items": {"type": "null"}}, [1]),
    ({"properties": {"a": {}}, "unevaluatedProperties": False}, {"a": 1, "c": 2, "b": 3}),
    ({"unevaluatedProperties": {"type": "integer", "minimum": 5}}, {"a": "x", "b": 1}),
    ({"prefixItems": [{}], "unevaluatedItems": False}, [1, 2, "a"]), ({"$schema": D19, "items": [{}], "unevaluatedItems": False}, [1, 2]),
    (False, 1), ({"properties": {"a": False}}, {"a": [1]}), (True, 1), ({}, {"a": 1}),
]
CHECKED = [{"type": "strin"}, {"type": ["string", "string"]}, {"required": "a"}, {"minItems": -1}, {"properties": 3}, {"pattern": "["},
           {"patternProperties": {"(": {}}}, {"allOf": []}, {"$id": "a#b"}, {"items": [1]}, {"enum": 3}, {"multipleOf": 0},
           {"$schema": D7, "items": [1]}, {"$schema": D7, "required": []}, {"$schema": D4, "required": []}, {"$schema": D4, "exclusiveMinimum": True},
           {"$schema": D19, "additionalItems": 3}, {"properties": {"a": {"properties": {"b": {"minLength": "1"}}}}}, {"type": "object"}]
NAMES = ["a", "b", "c", "ab", "x-1", "$id", "a b"]
STRINGS = ["", "a", "ab", "abc", "b1", "x-1", "A", "é", "aaa", "1", "true"]
PATTERNS = ["^a", "b$", "a|b", "^x-", "[0-9]+", "^$", "a{2}", "(", "[", "\\d", "^(ab)+$"]
TYPES = ["string", "number", "integer", "boolean", "null", "object", "array"]
SCHEMAS = [None, None, None, None, "http://json-schema.org/draft-07/schema#", "http://json-schema.org/draft-07/schema",
           "http://json-schema.org/draft-06/schema#", "http://json-schema.org/draft-04/schema#",
           "https://json-schema.org/draft/2019-09/schema", "https://json-schema.org/draft/2020-12/schema",
           "https://example.com/unknown", "HTTP://json-schema.org/draft-07/schema#"]


def value(rng, depth=0):
    kind = rng.randrange(11 if depth < 3 else 7)
    if kind == 0:
        return None
    if kind == 1:
        return rng.choice([True, False])
    if kind == 2:
        return rng.choice([0, 1, 2, 3, -1, 5, 10, 7, 100, 2**70])
    if kind == 3:
        return rng.choice([0.0, 1.0, 1.5, 2.5, -0.5, 3.0, 0.1, 1e300, 7.5])
    if kind in (4, 5, 6):
        return rng.choice(STRINGS)
    if kind in (7, 8):
        return [value(rng, depth + 1) for _ in range(rng.randrange(4))]
    return {rng.choice(NAMES): value(rng, depth + 1) for _ in range(rng.randrange(4))}


def number(rng):
    return rng.choice([0, 1, 2, 3, 5, 1.5, 2.5, 0.5, 10, -1, 0.1])


def count(rng):
    return rng.choice([0, 0, 1, 1, 2, 3])


def subschema(rng, depth, bad):
    if rng.random() < 0.08:
        return rng.choice([True, False])
    return schema(rng, depth + 1, bad)


def schema(rng, depth=0, bad=0.0, legacy=False):
    out = {}
    budget = rng.randrange(1, 5) if depth < 3 else rng.randrange(0, 2)
    for _ in range(budget):
        key = rng.choice(KEYS)
        if depth >= 3 and key in NESTING:
            key = "type"
        if rng.random() < bad:
            out[key] = rng.choice([value(rng, 2), -1, "x", [], {}, [1], None, 1.5, True])
            continue
        if key == "type":
            out[key] = rng.choice(TYPES) if rng.random() < 0.8 else rng.sample(TYPES, rng.randrange(1, 4))
        elif key in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
            names = PATTERNS[:7] if key == "patternProperties" else NAMES
            out[key] = {rng.choice(names): subschema(rng, depth, bad) for _ in range(rng.randrange(1, 4))}
        elif key == "required":
            out[key] = rng.sample(NAMES, rng.randrange(0, 3))
        elif key in ("items",):
            if rng.random() < 0.3:
                out[key] = [subschema(rng, depth, bad) for _ in range(rng.randrange(0, 3))]
            else:
                out[key] = subschema(rng, depth, bad)
        elif key in ("additionalProperties", "additionalItems", "contains", "not", "if", "then", "else", "propertyNames",
                     "unevaluatedItems", "unevaluatedProperties"):
            out[key] = subschema(rng, depth, bad)
        elif key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            out[key] = [subschema(rng, depth, bad) for _ in range(rng.randrange(1, 4))]
        elif key == "enum":
            out[key] = [value(rng, 2) for _ in range(rng.randrange(1, 4))]
        elif key == "const":
            out[key] = value(rng, 2)
        elif key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
            out[key] = number(rng) if rng.random() < 0.9 else rng.choice([True, False])
        elif key == "multipleOf":
            out[key] = rng.choice([1, 2, 3, 0.5, 0.1, 1.5, 2.0])
        elif key in ("minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties", "minContains",
                     "maxContains"):
            out[key] = count(rng)
        elif key == "uniqueItems":
            out[key] = rng.choice([True, True, False])
        elif key == "pattern":
            out[key] = rng.choice(PATTERNS)
        elif key == "format":
            out[key] = rng.choice(["regex", "date", "email", "uri", "nope"])
        elif key == "dependentRequired":
            out[key] = {rng.choice(NAMES): rng.sample(NAMES, rng.randrange(0, 3)) for _ in range(rng.randrange(1, 3))}
        elif key == "dependencies":
            out[key] = {rng.choice(NAMES): (rng.sample(NAMES, rng.randrange(1, 3)) if rng.random() < 0.5
                                           else subschema(rng, depth, bad)) for _ in range(rng.randrange(1, 3))}
        elif key in ("$ref", "$dynamicRef"):
            out[key] = rng.choice(["#", "#/$defs/a", "#/$defs/b", "#/definitions/a", "#/properties/a", "#/nope",
                                   "#/$defs/a%20b", "#/items/0", "#/allOf/1", "other.json", "#anchor", "#/$defs/x-1",
                                   "#/properties/a/items", "#/"])
        elif key == "$recursiveRef":
            out[key] = "#"
        elif key == "$id":
            out[key] = rng.choice(["https://example.com/root", "#frag", "sub.json", "https://example.com/root#"])
        elif key == "$schema":
            choice = rng.choice(SCHEMAS)
            if choice is not None:
                out[key] = choice
        elif key == "default":
            out[key] = value(rng, 2)
        elif key == "id":
            out[key] = rng.choice(["https://example.com/root", "#frag"])
    return out


NESTING = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas", "items", "additionalProperties",
           "additionalItems", "contains", "not", "if", "then", "else", "propertyNames", "unevaluatedItems",
           "unevaluatedProperties", "allOf", "anyOf", "oneOf", "prefixItems", "dependencies"}
KEYS = (["type"] * 8 + ["properties"] * 6 + ["required"] * 3 + ["items"] * 5 + ["enum", "const"] * 2
        + ["additionalProperties"] * 3 + ["allOf", "anyOf", "oneOf", "not", "if", "then", "else"] * 2
        + ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength", "maxLength",
           "pattern", "format", "minItems", "maxItems", "uniqueItems", "prefixItems", "additionalItems", "contains",
           "minContains", "maxContains", "minProperties", "maxProperties", "patternProperties", "propertyNames",
           "dependentRequired", "dependentSchemas", "dependencies", "unevaluatedItems", "unevaluatedProperties",
           "$defs", "definitions", "$ref", "$ref", "$ref", "$dynamicRef", "$recursiveRef", "$id", "id", "default"])




def outcome(errors, function, *arguments):
    """What a call returned or raised: a validation or schema error by its message alone."""
    try:
        return ("ok", function(*arguments))
    except errors as error:
        return (type(error).__name__, error.message)
    except RecursionError:
        return ("RecursionError", "")
    except Exception as error:  # (whatever either validator raises is compared)
        return (type(error).__name__, str(error))


def case(rng, number):
    """The schema of case number: every fourth with keyword values that no metaschema allows."""
    top = schema(rng, 0, 0.12 if number % 4 == 0 else 0.0)
    if rng.random() < 0.5:
        choice = rng.choice(SCHEMAS)
        if choice is not None:
            top = {"$schema": choice, **top}
    if rng.random() < 0.5 and isinstance(top.get("$defs", {}), dict):
        top.setdefault("$defs", {}).update({name: subschema(rng, 1, 0.0) for name in rng.sample(NAMES, 2)})
    return json.loads(json.dumps(top))


def unresolved(top, want, got):
    """Is got the port's error for a reference that it leaves out, as the module describes."""
    if got[0] not in ("_WrappedReferencingError", "Unresolvable"):
        return False
    if got[0] == "_WrappedReferencingError" and not got[1].startswith("Unresolvable"):
        return False
    text = json.dumps(top)
    return (want[0] in ("_WrappedReferencingError", "NoSuchAnchor", "Unresolvable", "PointerToNowhere")
            or '"$id"' in text or '"id"' in text)


def answers(validator_for, validation_error, schema_error):
    """What a validator module makes of PAIRS and CHECKED: for each pair None or the error's class
    and message, for each schema None or check_schema()'s message."""
    validated = []
    for schema, instance in PAIRS:
        dialect = validator_for(schema)
        dialect.check_schema(schema)
        try:
            dialect(schema).validate(instance)
            validated.append([schema, instance, None])
        except validation_error as error:
            validated.append([schema, instance, "ValidationError: " + error.message])
        except Exception as error:  # (an unresolvable reference, by its class and text)
            validated.append([schema, instance, type(error).__name__ + ": " + str(error)])
    checked = []
    for schema in CHECKED:
        try:
            validator_for(schema).check_schema(schema)
            checked.append([schema, None])
        except schema_error as error:
            checked.append([schema, error.message])
    return {"validate": validated, "check": checked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--schemas", type=int, default=20000)
    parser.add_argument("--instances", type=int, default=6, help="instances of each valid schema")
    parser.add_argument("--answers", type=Path, metavar="FILE", help="record jsonschema's answers and stop")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT / "ports"))
    sys.setrecursionlimit(400)
    warnings.simplefilter("ignore")
    import jsonschema
    from jsonschema import validators as theirs

    from json_repair._jsonschema import exceptions, validators as ours

    jsonschema._keywords.set = lambda names: list(dict.fromkeys(names))
    if args.answers:
        recorded = answers(theirs.validator_for, jsonschema.exceptions.ValidationError, jsonschema.exceptions.SchemaError)
        args.answers.write_text(json.dumps(dict(recorded, jsonschema=jsonschema.__version__), ensure_ascii=True) + "\n")
        return 0
    errors = (jsonschema.exceptions.ValidationError, jsonschema.exceptions.SchemaError, exceptions.ValidationError,
              exceptions.SchemaError)
    rng = random.Random(args.seed)
    stats = {"schemas": 0, "valid schemas": 0, "instances": 0, "invalid instances": 0, "raised": 0,
             "references left out": 0}
    bad = 0
    for number in range(args.schemas):
        top = case(rng, number)
        stats["schemas"] += 1
        theirs_class = outcome(errors, theirs.validator_for, top)
        if theirs_class[0] != "ok" or theirs_class[1].__name__ == "Draft3Validator":
            continue
        ours_class = ours.validator_for(top)
        want = outcome(errors, theirs_class[1].check_schema, top)
        got = outcome(errors, ours_class.check_schema, top)
        if want != got:
            bad += 1
            if bad <= 10:
                print("check_schema", json.dumps(top), "\n  jsonschema:", want, "\n  the port:  ", got)
            continue
        if want[0] != "ok":
            continue
        stats["valid schemas"] += 1
        theirs_validator = theirs_class[1](top)
        ours_validator = ours_class(top)
        for _ in range(args.instances):
            instance = value(rng)
            stats["instances"] += 1
            for attempt in ("validate", "is_valid"):
                want = outcome(errors, getattr(theirs_validator, attempt), instance)
                got = outcome(errors, getattr(ours_validator, attempt), instance)
                if attempt == "validate":
                    stats["invalid instances"] += want[0] == "ValidationError"
                    stats["raised"] += want[0] not in ("ok", "ValidationError")
                if want == got:
                    continue
                if unresolved(top, want, got):
                    stats["references left out"] += attempt == "validate"
                    continue
                bad += 1
                if bad <= 10:
                    print(attempt, json.dumps(top), "\n  instance:", json.dumps(instance), "\n  jsonschema:", want,
                          "\n  the port:  ", got)
    print(", ".join(f"{count} {name}" for name, count in stats.items()) + f"; {bad} differences")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
