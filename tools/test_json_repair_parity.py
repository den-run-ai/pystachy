"""Fail-closed controls for the json_repair native parity evidence."""
import copy
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_json_repair_corpus import calls_with_env, request


CHECKER = Path(__file__).with_name("json_repair_parity.py")


class JsonRepairExtractionTests(unittest.TestCase):
    def extract(self, source):
        return [request(node, env) for node, env in calls_with_env(ast.parse(source), {})]

    def test_preserves_api_and_serialization_options(self):
        self.assertEqual(self.extract('''
repair_json('{a: 1}', logging=True, ensure_ascii=False)
loads('{a: 1}', strict=True)
'''), [
            ('{a: 1}', {'return_objects': False, 'logging': True, 'ensure_ascii': False}, 'repair_json'),
            ('{a: 1}', {'strict': True}, 'loads'),
        ])

    def test_literal_loops_keep_every_variant(self):
        self.assertEqual(self.extract('''
cases = [('a', 'unused'), ('b', 'unused')]
for raw, expected in cases:
    for skip in (False, True):
        repair_json(raw, skip_json_loads=skip, return_objects=True)
'''), [
            (raw, {'return_objects': True, 'skip_json_loads': skip}, 'repair_json')
            for raw in ('a', 'b') for skip in (False, True)
        ])

    def test_does_not_evaluate_source_calls(self):
        for prefix in ('', "raw = '{}'; "):
            with self.subTest(prefix=prefix), self.assertRaises((ValueError, KeyError)):
                self.extract(prefix + "raw = arbitrary_call()\nrepair_json(raw)")

    def test_literal_helper_expansion(self):
        tree = ast.parse('''
def helper(raw, expected):
    repair_json(raw, return_objects=True)
def test_example():
    helper('{a: 1}', {'a': 1})
''')
        helper, test = tree.body
        found = [request(node, env) for node, env in calls_with_env(test, {}, {'helper': helper})]
        self.assertEqual(found, [('{a: 1}', {'return_objects': True}, 'repair_json')])

    def test_literal_condition_retains_each_input_variant(self):
        self.assertEqual(self.extract('''
for fenced in (False, True):
    raw = '{}'
    if fenced:
        raw = f'prefix {raw}'
    loads(raw)
'''), [('{}', {}, 'loads'), ('prefix {}', {}, 'loads')])

    def test_unsupported_options_are_not_silently_dropped(self):
        for source in ("repair_json('{}', indent=2)", "repair_json('{}', True)"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.extract(source)


class JsonRepairParityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        outcomes = [
            {"value": ["bool", True]},
            {"value": ["str", [0xD83D, 0xDE00]]},
            {"value": ["tuple", [
                ["dict", [[["str", [120]], ["float", (1e-6).hex()]]]],
                ["list", [["float", (-0.0).hex()]]],
            ]]},
            {"error": "ValueError", "message": "missing value"},
        ]
        self.cases = [
            {"id": i, "api": "repair_json", "input": "fixture", "flags": {},
             "sources": ["synthetic checker control"], "expected": outcome}
            for i, outcome in enumerate(outcomes)
        ]
        self.rows = [{"id": case["id"], **copy.deepcopy(case["expected"])} for case in self.cases]
        self.corpus = self.root / "cases.json"
        self.corpus.write_text(json.dumps(self.cases))

    def check(self, rows, *, suffix="", passes=False):
        output = self.root / "output.jsonl"
        output.write_text("".join(json.dumps(row) + "\n" for row in rows) + suffix)
        report_path = self.root / "report.json"
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(output), "--cases", str(self.corpus),
             "--report", str(report_path)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0 if passes else 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(report_path.read_text())
        self.assertEqual(report["cases"], len(self.cases))
        self.assertEqual(bool(report["problems"]), not passes)
        if passes:
            self.assertEqual(report["matched"], len(self.cases))
        return report

    def test_exact_output_passes(self):
        self.check(self.rows, passes=True)

    def test_missing_case_fails(self):
        report = self.check(self.rows[:-1])
        self.assertEqual(report["matched"], 3)
        self.assertEqual(report["problems"][0]["actual"], {"error": "missing case"})

    def test_duplicate_case_fails_even_when_all_cases_match(self):
        report = self.check(self.rows + [self.rows[0]])
        self.assertEqual(report["matched"], 4)
        self.assertIn("duplicate", report["problems"][0]["error"])

    def test_extra_case_fails_even_when_all_cases_match(self):
        report = self.check(self.rows + [{"id": 99, "value": ["none"]}])
        self.assertEqual(report["matched"], 4)
        self.assertEqual(report["problems"][0]["error"], "unexpected case id")

    def test_malformed_output_fails(self):
        for suffix in ("{broken\n", "null\n", "[]\n", '{"value":["none"]}\n'):
            with self.subTest(suffix=suffix):
                report = self.check(self.rows, suffix=suffix)
                self.assertEqual(report["matched"], 4)

    def test_boolean_is_not_an_integer(self):
        self.rows[0]["value"] = ["bool", 1]
        self.check(self.rows)
        self.rows[0]["value"] = ["int", "1"]
        self.check(self.rows)

    def test_surrogate_pair_is_not_one_astral_character(self):
        self.rows[1]["value"] = ["str", [0x1F600]]
        self.check(self.rows)

    def test_float_notation_normalizes_but_zero_sign_is_preserved(self):
        self.rows[2]["value"] = ["tuple", [
            ["dict", [[["str", [120]], ["float-repr", "0.000001"]]]],
            ["list", [["float-repr", "-0.0"]]],
        ]]
        self.check(self.rows, passes=True)
        self.rows[2]["value"][1][1][1][0][1] = "0.0"
        self.check(self.rows)

    def test_exception_message_must_match(self):
        self.rows[3]["message"] = "different error"
        self.check(self.rows)


if __name__ == "__main__":
    unittest.main()
