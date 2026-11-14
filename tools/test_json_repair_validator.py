"""The json_repair port's JSON Schema validator, where no jsonschema is installed: against
jsonschema's recorded answers, and for what it raises on generated schemas."""
import json
import random
import sys
import unittest

import json_repair_validator_fuzz as fuzz

sys.path.insert(0, str(fuzz.ROOT / "ports"))
from json_repair._jsonschema import exceptions, validators


class AnswerTests(unittest.TestCase):
    def test_the_recorded_answers_are_those_of_the_table(self):
        recorded = json.loads(fuzz.ANSWERS.read_text())
        self.assertEqual(recorded["jsonschema"], "4.26.0")
        self.assertEqual([row[:2] for row in recorded["validate"]], json.loads(json.dumps([list(pair) for pair in fuzz.PAIRS])))
        self.assertEqual([row[0] for row in recorded["check"]], json.loads(json.dumps(fuzz.CHECKED)))
        # Every keyword's error is among them, and some instances that are valid.
        messages = " ".join(str(row[2]) for row in recorded["validate"])
        for words in ("is not of type", "is a required property", "Additional properties", "does not match any of the regexes",
                      "is a dependency of", "Expected at most", "Additional items", "has non-unique elements",
                      "does not contain items", "Too few items", "Too many items", "None of", "is not one of",
                      "was expected", "less than the minimum", "greater than the maximum", "less than or equal to",
                      "greater than or equal to", "is not a multiple of", "should be non-empty", "is too short",
                      "is expected to be empty", "is too long", "does not match", "does not have enough properties",
                      "has too many properties", "not valid under any", "is valid under each of", "should not be valid",
                      "PointerToNowhere", "Unevaluated properties are not allowed",
                      "Unevaluated properties are not valid", "Unevaluated items", "False schema does not allow"):
            self.assertIn(words, messages)
        self.assertGreater(sum(row[2] is None for row in recorded["validate"]), 5)

    def test_the_validator_gives_jsonschemas_answers(self):
        recorded = json.loads(fuzz.ANSWERS.read_text())
        ours = fuzz.answers(validators.validator_for, exceptions.ValidationError, exceptions.SchemaError)
        for want, got in zip(recorded["validate"], ours["validate"], strict=True):
            self.assertEqual(json.loads(json.dumps(got)), want)
        for want, got in zip(recorded["check"], ours["check"], strict=True):
            self.assertEqual(json.loads(json.dumps(got)), want)

    def test_references_that_are_left_out_fail(self):
        for schema, text in (({"$ref": "#name", "$defs": {"a": {"$dynamicAnchor": "name"}}}, "Unresolvable: #name"),
                             ({"$schema": fuzz.D7, "$ref": "#name", "definitions": {"a": {"$id": "#name"}}},
                              "Unresolvable: #name"),
                             ({"$ref": "#name", "$defs": {"a": {"$anchor": "name"}, "b": {"$anchor": "name"}}},
                              "Unresolvable: #name"),
                             ({"$ref": "other.json"}, "Unresolvable: other.json"),
                             ({"$ref": "https://example.com/a#/b"}, "Unresolvable: https://example.com/a#/b"),
                             ({"properties": {"a": {"$id": "https://example.com/a", "$ref": "#/$defs/n"}},
                               "$defs": {"n": {}}}, "Unresolvable: #/$defs/n")):
            dialect = validators.validator_for(schema)
            dialect.check_schema(schema)
            with self.assertRaises(exceptions._WrappedReferencingError) as raised:
                dialect(schema).validate({"a": 1})
            self.assertEqual(str(raised.exception), text)
            self.assertNotIsInstance(raised.exception, ValueError)  # (json_repair takes a ValueError for a mismatch)
        own = {"$id": "https://example.com/root", "$ref": "https://example.com/root#/$defs/n", "$defs": {"n": {"type": "null"}}}
        self.assertTrue(validators.validator_for(own)(own).is_valid(None))
        draft3 = {"$schema": "http://json-schema.org/draft-03/schema#"}
        with self.assertRaisesRegex(exceptions.SchemaError, "Draft 3"):
            validators.validator_for(draft3).check_schema(draft3)
        self.assertEqual(sorted(validators.METASCHEMAS), [4, 6, 7, 2019, 2020])

    def test_static_anchors_are_found_only_in_schema_positions(self):
        for draft in (fuzz.D19, fuzz.D20):
            singles = ("additionalProperties", "contains", "contentSchema", "else", "if", "items", "not",
                       "propertyNames", "then", "unevaluatedItems", "unevaluatedProperties")
            arrays = ("allOf", "anyOf", "oneOf") + (("prefixItems",) if draft == fuzz.D20 else ())
            maps = ("$defs", "definitions", "dependentSchemas", "patternProperties", "properties")
            anchor = {"$anchor": "target", "type": "integer"}
            for keyword in singles + arrays + maps:
                child = [anchor] if keyword in arrays else {"a": anchor} if keyword in maps else anchor
                schema = {"$schema": draft, keyword: child}
                validator = validators.validator_for(schema)(schema)
                self.assertEqual(validator._resolve("#target", validator._draft, False), (anchor, False), keyword)
            for keyword in ("const", "default", "enum", "examples", "unknown"):
                schema = {"$schema": draft, keyword: [anchor] if keyword in ("enum", "examples") else anchor}
                validator = validators.validator_for(schema)(schema)
                with self.assertRaises(exceptions.NoSuchAnchor, msg=keyword):
                    validator._resolve("#target", validator._draft, False, False)

    def test_evolve_retains_the_root_anchor_dialect(self):
        root = {"$id": "https://example.com/root", "$defs": {"n": {"$anchor": "n", "type": "integer"}}}
        validator = validators.validator_for(root)(root)
        for draft in (fuzz.D4, fuzz.D7, fuzz.D19, fuzz.D20):
            for ref in ("#n", "https://example.com/root#n"):
                evolved = validator.evolve({"$schema": draft, "$ref": ref})
                self.assertTrue(evolved.is_valid(3))
                self.assertFalse(evolved.is_valid("x"))

    def test_embedded_resources_cannot_shadow_root_anchors(self):
        for child_id in ("", "#", "https://example.com/root", "https://example.com/root#", "other.json"):
            for reverse in (False, True):
                definitions = {"nested": {"$id": child_id, "$anchor": "n", "type": "string"},
                               "outer": {"$anchor": "n", "type": "integer"}}
                if reverse:
                    definitions = dict(reversed(list(definitions.items())))
                root = {"$id": "https://example.com/root", "$defs": definitions, "$ref": "#n"}
                validator = validators.validator_for(root)(root)
                for instance in (3, "x"):
                    with self.assertRaisesRegex(exceptions._WrappedReferencingError, "Unresolvable: #n"):
                        validator.validate(instance)


class GeneratedTests(unittest.TestCase):
    def test_cases_are_deterministic_json(self):
        rng, again = random.Random(5), random.Random(5)
        first = [fuzz.case(rng, number) for number in range(200)]
        self.assertEqual(first, [fuzz.case(again, number) for number in range(200)])
        self.assertEqual(first, json.loads(json.dumps(first)))
        self.assertGreater(len({json.dumps(each, sort_keys=True) for each in first}), 150)

    def test_the_validator_raises_only_what_it_documents(self):
        rng = random.Random(9)
        allowed = (exceptions.ValidationError, exceptions.SchemaError, exceptions._WrappedReferencingError,
                   exceptions.Unresolvable, RecursionError,
                   # as jsonschema: a $ref that is no str, a pointer segment that is no index, an
                   # unhashable or unordered comparison of a schema that its metaschema lets through
                   AttributeError, ValueError, TypeError)
        valid = invalid = 0
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(400)
        try:
            for number in range(1500):
                schema = fuzz.case(rng, number)
                dialect = validators.validator_for(schema)
                try:
                    dialect.check_schema(schema)
                except exceptions.SchemaError as error:
                    self.assertIsInstance(error.message, str)
                    invalid += 1
                    continue
                valid += 1
                validator = dialect(schema)
                for _ in range(3):
                    instance = fuzz.value(rng)
                    try:
                        self.assertIsInstance(validator.is_valid(instance), bool)
                        validator.validate(instance)
                    except allowed:
                        pass
        finally:
            sys.setrecursionlimit(limit)
        self.assertGreater(valid, 700)
        self.assertGreater(invalid, 250)

    def test_a_reference_left_out_is_told_from_a_difference(self):
        embedded = {"properties": {"a": {"$id": "x", "$ref": "#"}}}
        self.assertTrue(fuzz.unresolved(embedded, ("ok", True), ("_WrappedReferencingError", "Unresolvable: #")))
        self.assertTrue(fuzz.unresolved({"$ref": "#a"}, ("_WrappedReferencingError", "NoSuchAnchor: ..."),
                                        ("_WrappedReferencingError", "Unresolvable: #a")))
        self.assertFalse(fuzz.unresolved({"$ref": "#/a"}, ("ok", True), ("_WrappedReferencingError", "Unresolvable: #/a")))
        self.assertFalse(fuzz.unresolved(embedded, ("ok", True), ("ValidationError", "1 is not of type 'null'")))
        self.assertFalse(fuzz.unresolved(embedded, ("ok", True), ("_WrappedReferencingError", "PointerToNowhere: '/a' ...")))


if __name__ == "__main__":
    unittest.main()
