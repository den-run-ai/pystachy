"""Keep the CPython companion benchmark's results and request mix honest."""
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("companion_bench", ROOT / "bench/json_repair/companion.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class CompanionBenchmarkTests(unittest.TestCase):
    def test_validation_rejects_equal_but_differently_typed_values(self):
        for expected, actual in ((1, True), (1, 1.0), ([1], (1,)), (0.0, -0.0)):
            with self.subTest(expected=expected, actual=actual):
                with self.assertRaises(ValueError):
                    bench.validate([actual], [bench.tagged(expected)])

    def test_validation_rejects_lost_order_logs_and_unicode(self):
        for expected, actual in (
            ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
            (({"a": 1}, [{"text": "repaired", "context": "{a:1}"}]), ({"a": 1}, [])),
            ("\ud83d\ude00", "\U0001f600"),
        ):
            with self.subTest(expected=expected, actual=actual):
                with self.assertRaises(ValueError):
                    bench.validate([actual], [bench.tagged(expected)])

    def test_missing_result_cannot_pass_complete_validation(self):
        with self.assertRaises(ValueError):
            bench.validate([1], [bench.tagged(1), bench.tagged(2)])

    def test_mix_has_exact_counts_and_equal_malformed_weights(self):
        document = json.loads(bench.CASES.read_text())
        rows = bench.select_cases(document, "mixed")
        self.assertEqual(len(rows), 20)
        self.assertEqual(sum(row["valid"] for row in rows), 16)
        self.assertEqual([row["id"] for row in rows if not row["valid"]],
                         [f"malformed-{index}" for index in range(4)])
        self.assertEqual(len(bench.select_cases(document, "malformed")), 4)
        for row in rows:
            self.assertEqual(set(row["expected"]), {"text", "objects", "logs"})

    def test_incomplete_fixture_is_rejected(self):
        document = json.loads(bench.CASES.read_text())
        document["cases"].pop()
        with self.assertRaises(ValueError):
            bench.select_cases(document, "mixed")


if __name__ == "__main__":
    unittest.main()
