"""Fail-closed controls for the json_repair native parity evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).with_name("json_repair_parity.py")


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
