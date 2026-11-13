"""Fail-closed controls for the json_repair differential fuzz."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import json_repair_fuzz as fuzz


class GenerationTests(unittest.TestCase):
    seeds = fuzz.corpus_seeds(json.loads(fuzz.CASES.read_text()))

    def test_requests_are_deterministic_and_complete(self):
        for family in fuzz.FAMILIES:
            with self.subTest(family=family):
                rows = fuzz.requests(7, 301, family, self.seeds)
                self.assertEqual(rows, fuzz.requests(7, 301, family, self.seeds))
                self.assertNotEqual(rows, fuzz.requests(8, 301, family, self.seeds))
                self.assertEqual([row["id"] for row in rows], list(range(301)))
                self.assertGreater(len({row["input"] for row in rows}), 80)

    def test_requests_use_only_what_the_replay_program_passes_on(self):
        replay = fuzz.REPLAY.read_text()
        for api, flags in fuzz.FLAGS:
            self.assertIn(api, ("repair_json", "loads"))
            for name in flags:
                self.assertIn(f'flags.get("{name}"', replay)
            if api == "loads":
                # loads() takes neither option; the replay program would drop it without a word.
                self.assertFalse({"return_objects", "ensure_ascii"} & set(flags))
        used = {(api, name) for api, flags in fuzz.FLAGS for name in flags}
        for row in fuzz.requests(1, 600, "mixed", self.seeds):
            self.assertIn((row["api"], row["flags"]), fuzz.FLAGS)
        self.assertEqual({name for _, name in used},
                         {"return_objects", "skip_json_loads", "logging", "strict", "stream_stable", "ensure_ascii"})

    def test_schema_requests_pass_a_schema_in_each_mode(self):
        replay = fuzz.REPLAY.read_text()
        rows = fuzz.requests(1, 2400, "schema", self.seeds)
        examples = sum(2 * len(modes) for _, _, modes in fuzz.EXAMPLES)
        self.assertEqual([(row["input"], row["flags"]["schema"]) for row in rows[:examples:2]],
                         [(text, schema) for text, schema, modes in fuzz.EXAMPLES for _ in modes])
        names = set()
        for row in rows:
            self.assertIn("schema", row["flags"])
            names |= set(row["flags"])
            if row["api"] == "loads":
                self.assertFalse({"return_objects", "ensure_ascii"} & set(row["flags"]))
        for name in names:
            self.assertIn(f'flags.get("{name}"', replay)
        self.assertEqual({row["flags"].get("schema_repair_mode") for row in rows}, {None, "standard", "salvage", "quick"})
        schemas = json.dumps([row["flags"]["schema"] for row in rows[examples:]])
        for keyword in ("$ref", "$defs", "anyOf", "oneOf", "allOf", "prefixItems", "additionalItems", "patternProperties",
                        "additionalProperties", "required", "enum", "const", "default", "minItems", "$schema", "not",
                        "unevaluatedProperties", "dependentRequired", "propertyNames", "multipleOf", "pattern"):
            self.assertIn(f'"{keyword}"', schemas)
        self.assertTrue(any(row["flags"]["schema"] is False for row in rows))
        # The oracle's pins name the two modules whose sets of names upstream iterates.
        compile(fuzz.PINNED, "pinned.py", "exec")
        for module in ("jsonschema._keywords.set = ordered", "json_repair.parser_schema.set = ordered"):
            self.assertIn(module, fuzz.PINNED)

    def test_texts_survive_json_transport(self):
        for family in fuzz.FAMILIES:
            for row in fuzz.requests(3, 600, family, self.seeds):
                self.assertEqual(json.loads(json.dumps(row))["input"], row["input"])
                self.assertFalse(any(0xD800 <= ord(char) <= 0xDFFF for char in row["input"]))

    def test_families_reach_the_scanners_boundaries(self):
        long = [row["input"] for row in fuzz.requests(1, 900, "long", self.seeds)]
        self.assertTrue(any(len(text) > 2 * fuzz.CHUNKS[-1] for text in long))
        self.assertTrue(any("\\" in text[60:68] or '"' in text[60:68] for text in long))
        comments = [row["input"] for row in fuzz.requests(1, 900, "comment", self.seeds)]
        for opener in ("//", "#", "/*"):
            self.assertTrue(any(opener in text and len(text) > fuzz.WINDOWS[-1] for text in comments), opener)
        numbers = [row["input"] for row in fuzz.requests(1, 900, "number", self.seeds)]
        self.assertTrue(any(sum(char.isdigit() for char in text) > 19 for text in numbers))


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.files = 0

    def output(self, *rows):
        self.files += 1
        path = self.scratch / f"{self.files}.out"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return path

    def test_outputs_need_one_row_for_each_case_in_order(self):
        first = {"id": 0, "value": ["int", "1"]}
        second = {"id": 1, "error": "ValueError", "message": "no"}
        self.assertEqual(fuzz.checked(self.output(first, second), 2), 1)
        for rows, count in (((first,), 2), ((first, first), 2), ((first, second), 1), ((second, first), 2),
                            ((first, {"id": 1}), 2), (({"id": False, "value": ["none"]},), 1),
                            ((first, dict(second, value=["none"])), 2)):
            with self.assertRaises(ValueError, msg=rows):
                fuzz.checked(self.output(*rows), count)
            with self.assertRaises(ValueError, msg=rows):
                fuzz.differing(self.output(first, second), self.output(*rows), count)

    def test_differences_are_type_exact(self):
        error = {"id": 1, "error": "ValueError", "message": "strict"}
        oracle = self.output({"id": 0, "value": ["list", [["bool", True], ["float-repr", "1.0"]]]}, error)
        self.assertEqual(fuzz.differing(oracle, oracle, 2), ([], {}))
        # The oracle may hold more rows than a stressed replay of the first cases.
        self.assertEqual(fuzz.differing(oracle, self.output({"id": 0, "value": ["list", [["bool", True],
                                                                                    ["float-repr", "1.00"]]]}), 1), ([], {}))
        for changed in ({"id": 0, "value": ["list", [["bool", 1], ["float-repr", "1.0"]]]},
                        {"id": 0, "value": ["list", [["bool", True], ["float-repr", "1.0000000000000002"]]]},
                        {"id": 0, "value": ["tuple", [["bool", True], ["float-repr", "1.0"]]]},
                        {"id": 0, "error": "ValueError", "message": "strict"}):
            bad, kept = fuzz.differing(oracle, self.output(changed, error), 2)
            self.assertEqual((bad, list(kept)), ([0], [0]), changed)
            self.assertEqual(kept[0], {"value": ["list", [["bool", True], ["float", (1.0).hex()]]]})
        self.assertEqual(fuzz.differing(oracle, self.output({"id": 0, "error": "ValueError", "message": "strict"},
                                                            dict(error, message="Strict")), 2)[0], [0, 1])

    def test_a_recorded_sample_keeps_the_examples_and_each_kind_of_outcome(self):
        rows = fuzz.requests(1, 600, "schema", GenerationTests.seeds)
        examples = sum(2 * len(modes) for _, _, modes in fuzz.EXAMPLES)
        outcomes = []
        for row in rows:
            if row["id"] % 7 == 0:
                what = "integer" if row["id"] < examples else "number"
                outcomes.append({"id": row["id"], "error": "ValueError", "message": f"Expected {what} at $.k{row['id']}."})
            elif row["id"] % 7 == 1:
                outcomes.append({"id": row["id"], "error": "_WrappedReferencingError", "message": "Unresolvable: x"})
            else:
                outcomes.append({"id": row["id"], "value": ["dict", []]})
        kept = fuzz.sample(rows, self.output(*outcomes))
        self.assertEqual([row["id"] for row in kept], list(range(len(kept))))
        self.assertEqual([row["input"] for row in kept[:20]],
                         [row["input"] for row in rows[:examples:2] if row["id"] % 7 != 1][:20])
        later = [row for row in kept if row["input"] not in {row["input"] for row in rows[:examples]}]
        # One "Expected number" error stands for all of them, and no unresolvable reference is kept.
        self.assertEqual(len([row for row in later if "error" in row["expected"]]), 1)
        self.assertFalse(any(row["expected"].get("error") == "_WrappedReferencingError" for row in kept))
        self.assertTrue(all("id" not in row["expected"] for row in kept))
        self.assertLess(len(later), 40)  # (one value for each type, API and mode)
        with self.assertRaises(ValueError):
            fuzz.sample(rows, self.output(*outcomes[:-1]))

    def test_oracle_sources_are_checked_by_hash(self):
        manifest = json.loads(fuzz.MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as scratch:
            with self.assertRaisesRegex(ValueError, "is not json_repair"):
                fuzz.check_upstream(Path(scratch))
            for relative in manifest["source_sha256"]:
                path = Path(scratch) / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# not upstream\n")
            with self.assertRaisesRegex(ValueError, "is not json_repair"):
                fuzz.check_upstream(Path(scratch))

    def test_hosted_replay_of_the_port_is_compared(self):
        rows = fuzz.requests(1, 60, "mixed", GenerationTests.seeds)
        inputs = self.scratch / "inputs.jsonl"
        inputs.write_text("".join(json.dumps(row) + "\n" for row in rows))
        env = fuzz.hosted_env(fuzz.ROOT / "ports")
        command = [sys.executable, str(fuzz.REPLAY)]
        actual = fuzz.replayed("port, once", command, env, inputs, 120)
        self.assertEqual(fuzz.checked(actual, 60), sum('"error"' in line for line in actual.read_text().splitlines()))
        self.assertEqual(fuzz.differing(actual, fuzz.replayed("port, again", command, env, inputs, 120), 60), ([], {}))
        lines = actual.read_text().splitlines(keepends=True)
        changed = self.scratch / "changed.out"
        changed.write_text("".join(lines[:17] + [json.dumps({"id": 17, "value": ["str", [0x1F600]]}) + "\n"] + lines[18:]))
        self.assertEqual(fuzz.differing(actual, changed, 60)[0], [17])
        inputs.write_text("".join(json.dumps(row) + "\n" for row in rows[:59]))
        with self.assertRaisesRegex(ValueError, "no outcome for case 59"):
            fuzz.differing(actual, fuzz.replayed("port, short", command, env, inputs, 120), 60)
        with self.assertRaisesRegex(ValueError, "no program: exit 2"):
            fuzz.replayed("no program", [sys.executable, str(self.scratch / "missing.py")], env, inputs, 120)
        with self.assertRaisesRegex(ValueError, "CPython imports"):
            fuzz.hosted_env(self.scratch)


class RunTests(unittest.TestCase):
    def test_a_replay_that_fails_keeps_the_report_and_fails_the_run(self):
        # The port stands in for upstream, and a compiler that builds nothing for the native build:
        # the hosted comparison still reports, and the run fails closed with its report written.
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        compiler = Path(scratch.name) / "compiler"
        compiler.write_text("#!/bin/sh\nexit 0\n")
        compiler.chmod(0o755)
        report = Path(scratch.name) / "report.json"
        hosted_env = fuzz.hosted_env
        with mock.patch.object(fuzz, "check_upstream", lambda upstream: "v0"), \
                mock.patch.object(fuzz, "hosted_env", lambda parent: hosted_env(fuzz.ROOT / "ports")), \
                contextlib.redirect_stdout(io.StringIO()) as printed:
            status = fuzz.main(["--upstream", scratch.name, "--compiler", str(compiler), "--cases", "30",
                                "--family", "number", "--report", str(report)])
        self.assertEqual(status, 1)
        result = json.loads(report.read_text())
        self.assertEqual(result["result"], "fail")
        differences = result["families"]["number"]["differences"]
        self.assertEqual(differences["port under CPython"], [])
        self.assertIn("error", differences["native AOT"])
        self.assertIn("number: port under CPython: 30/30 match upstream v0", printed.getvalue())
        self.assertIn("number: native AOT: no result", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
