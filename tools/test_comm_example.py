"""Failure-path tests for the optional communication example's check harness."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comm_check", ROOT / "examples" / "comm" / "check.py")
assert SPEC is not None and SPEC.loader is not None
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class HarnessTests(unittest.TestCase):
    def test_oracle_uses_independent_arithmetic(self):
        output = CHECK.oracle_output(3)
        self.assertIn(b"allreduce [10.0, 14.0, -6.0]\n", output)
        self.assertIn(b"owned buffers, nested views, zero lengths 3\n", output)
        CHECK.compare_output("self", output, output)

    def test_oracle_preserves_source_order_float_addition(self):
        self.assertEqual(CHECK.ordered_column_sums([[1e16], [1.0], [-1e16]]), [0.0])
        self.assertEqual(CHECK.ordered_column_sums([[1e16], [-1e16], [1.0]]), [1.0])

    def test_comparison_rejects_truncation_and_extra_output(self):
        expected = CHECK.oracle_output(1)
        for actual in [expected[:-1], expected + b"extra", b""]:
            with self.subTest(actual=actual):
                with self.assertRaises(AssertionError):
                    CHECK.compare_output("bad", actual, expected)

    def test_successful_subprocess(self):
        output = CHECK.run([sys.executable, "-c", "print('ok')"], os.environ.copy())
        self.assertEqual(output, b"ok\n")

    def test_nonzero_exit_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "exited 7"):
            CHECK.run([sys.executable, "-c", "raise SystemExit(7)"], os.environ.copy())

    def test_stderr_fails_even_with_success_exit(self):
        with self.assertRaisesRegex(RuntimeError, "diagnostic"):
            CHECK.run([sys.executable, "-c", "import sys; sys.stderr.write('diagnostic')"], os.environ.copy())

    def test_timeout_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            CHECK.run([sys.executable, "-c", "import time; time.sleep(60)"], os.environ.copy(), timeout=0.05)

    def test_source_change_is_a_failure(self):
        report = {}
        with patch.object(CHECK, "source_hashes", return_value={"input": "new"}):
            with self.assertRaisesRegex(RuntimeError, "sources changed"):
                CHECK.verify_sources({"input": "old"}, report)
        self.assertEqual(report["sources_after"], {"input": "new"})

    def test_unchanged_sources_pass(self):
        report = {}
        with patch.object(CHECK, "source_hashes", return_value={"input": "same"}):
            CHECK.verify_sources({"input": "same"}, report)
        self.assertEqual(report["sources_after"], {"input": "same"})

    def test_failed_check_overwrites_stale_success_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text('{"result":"pass"}')
            with patch.object(CHECK, "check", side_effect=RuntimeError("failed probe")):
                with patch("sys.stderr"):
                    self.assertEqual(CHECK.main(["--report", str(report)]), 1)
            stored = json.loads(report.read_text())
            self.assertEqual(stored["result"], "fail")
            self.assertEqual(stored["error"], "failed probe")

    def test_invalid_options_fail_before_build(self):
        with patch.object(CHECK, "source_hashes", side_effect=AssertionError("unexpected build")):
            with patch("sys.stderr"):
                for args in [["--repeat", "0"], ["--repeat", "65"], ["--leak-check"]]:
                    with self.subTest(args=args):
                        self.assertEqual(CHECK.main(args), 1)


if __name__ == "__main__":
    unittest.main()
