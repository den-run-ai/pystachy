"""Fail-closed benchmark evidence parsing; no timings are performance gates."""
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "bench/text_kernels/run.py"
spec = importlib.util.spec_from_file_location("text_kernel_runner", path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class WitnessTests(unittest.TestCase):
    def test_only_clock_fields_are_ignored(self):
        good = "case x 17\nfirst 42 100\nwarmup 42\nsample 42 200\nverified 42\n"
        other_clock = good.replace("42 100", "42 999").replace("42 200", "42 1")
        self.assertEqual(runner.witness(good), runner.witness(other_clock))
        for old, new in [("case x 17", "case x 18"), ("first 42", "first 41"),
                         ("warmup 42", "warmup 0"), ("sample 42", "sample 0"),
                         ("verified 42", "verified 0")]:
            self.assertNotEqual(runner.witness(good), runner.witness(good.replace(old, new)))
        self.assertNotEqual(runner.witness(good), runner.witness(good + "unexpected diagnostic\n"))

    def test_missing_or_duplicate_samples_fail(self):
        for text in ["verified 42\n", "sample 42 1\nsample 42 2\n", "sample 42 -1\n"]:
            with self.assertRaises(ValueError):
                runner.measure(text)

    def test_malformed_clock_records_fail(self):
        for text in ["sample\n", "sample 42 nope\n", "first 42 1 extra\n"]:
            with self.assertRaises(ValueError):
                runner.witness(text)


if __name__ == "__main__":
    unittest.main()
