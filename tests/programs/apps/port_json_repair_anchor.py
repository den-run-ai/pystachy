# pystachy: dynamic-any
# Inputs are jsonschema 4.26's answers, recorded with CPython 3.13.16 by
# tools/json_repair_validator_fuzz.py --answers, for its ANCHOR_PAIRS.
import json
import sys
from typing import Any

from json_repair import loads
from json_repair._jsonschema.exceptions import ValidationError
from json_repair._jsonschema.validators import validator_for


checked = 0
different = 0
for line in sys.stdin:
    case: Any = json.loads(line)
    schema: Any = case[0]
    instance: Any = case[1]
    expected: Any = case[2]
    got: Any = None
    try:
        validator_for(schema)(schema).validate(instance)
    except ValidationError as error:
        got = "ValidationError: " + error.message
    except Exception as error:
        got = type(error).__name__ + ": " + str(error)
    if got != expected:
        print("difference", checked, json.dumps(got), json.dumps(expected))
        different += 1
    checked += 1
print(checked, "anchor cases;", different, "differences")

root: Any = {"$id": "https://example.com/root", "$defs": {"n": {"$anchor": "n", "type": "integer"}}}
validator = validator_for(root)(root)
matched = 0
for draft in ("http://json-schema.org/draft-04/schema#", "http://json-schema.org/draft-07/schema#",
              "https://json-schema.org/draft/2019-09/schema", "https://json-schema.org/draft/2020-12/schema"):
    for ref in ("#n", "https://example.com/root#n"):
        subschema: Any = {"$schema": draft, "$ref": ref}
        evolved = validator.evolve(schema=subschema)
        if evolved.is_valid(3) and not evolved.is_valid("x"):
            matched += 1
print(matched, "cross-draft evolved validators")

# The public facade validates an already-conforming value with an anchored schema. Upstream's
# repair algorithm itself still accepts only pointer references when it repairs malformed text.
schema: Any = {"type": "object", "properties": {"a": {"$ref": "#n"}},
               "$defs": {"n": {"$anchor": "n", "type": "integer"}}}
print(loads('{"a": 1}', schema=schema))
try:
    print(loads('{a: 2,}', schema=schema))
except Exception as error:
    print(type(error).__name__ + ": " + str(error))
