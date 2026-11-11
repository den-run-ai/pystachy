"""Independent failure-sensitivity checks for the upstream qualification controls."""
import contextlib
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pytest_native_controls as controls


class ControlQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pytest-controls-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def qualify(self, source=None, seed=104729):
        with patch.object(controls, "SOURCE", controls.SOURCE if source is None else source):
            return controls.qualify(self.work, ["python"], [], sys.executable, 15, seed)

    def test_seeded_positive_and_negative_controls_match_real_pytest(self):
        evidence = self.qualify()
        self.assertEqual(evidence["state"], "matched", evidence)
        self.assertEqual(len(evidence["cases"]), 30)
        self.assertEqual(evidence["excluded_cases"], [])
        self.assertEqual(evidence["oracle"]["exit_code"], 1)
        self.assertEqual(len([event for event in evidence["oracle"]["events"]
                              if event["outcome"] == "failed"]), 14)
        self.assertEqual(len([event for event in evidence["oracle"]["events"]
                              if event["outcome"] == "xfailed"]), 1)

    def test_runtime_input_changes_without_changing_test_source(self):
        first = self.qualify(seed=0)
        second = self.qualify(seed=2147483647)
        self.assertEqual(first["state"], "matched", first)
        self.assertEqual(second["state"], "matched", second)
        self.assertEqual(first["source_sha256"], second["source_sha256"])
        self.assertNotEqual(first["input_sha256"], second["input_sha256"])

    def test_agreement_is_not_enough_when_wrong_expectation_starts_passing(self):
        source = controls.SOURCE.replace("(seed ^ salt) + 1]", "(seed ^ salt) + 0]")
        self.assertNotEqual(source, controls.SOURCE)
        evidence = self.qualify(source)
        self.assertEqual(evidence["state"], "error")
        self.assertIn("independent control inventory", evidence["results"][0]["error"])

    def test_removed_positive_cases_do_not_reduce_the_inventory(self):
        source = controls.SOURCE.replace("def test_unicode_ok(", "def helper_unicode_ok(")
        evidence = self.qualify(source)
        self.assertEqual(evidence["state"], "error")
        self.assertIn("independent control inventory", evidence["results"][0]["error"])

    def test_fixture_cleanup_must_continue_after_a_failure(self):
        source = controls.SOURCE.replace('    cleanup_events.append("bad first cleanup")\n', "")
        evidence = self.qualify(source)
        self.assertEqual(evidence["state"], "error")
        event = next(event for event in evidence["oracle"]["events"]
                     if event["nodeid"].endswith("test_cleanup_wrong_seen") and event["phase"] == "call")
        self.assertEqual(event["outcome"], "failed")

    def test_swallowed_cleanup_errors_do_not_qualify(self):
        source = controls.SOURCE.replace('    raise ValueError("first cleanup failed")\n', "")
        source = source.replace('    raise RuntimeError("second cleanup failed")\n', "")
        evidence = self.qualify(source)
        self.assertEqual(evidence["state"], "error")
        event = next(event for event in evidence["oracle"]["events"]
                     if event["nodeid"].endswith("test_cleanup_wrong") and event["phase"] == "teardown")
        self.assertEqual(event["outcome"], "passed")

    def test_strict_xpass_cannot_become_a_nonfailing_xpass(self):
        source = controls.SOURCE.replace('reason="deliberate strict XPASS", strict=True',
                                         'reason="deliberate strict XPASS", strict=False')
        evidence = self.qualify(source)
        self.assertEqual(evidence["state"], "error")
        event = next(event for event in evidence["oracle"]["events"]
                     if event["nodeid"].endswith("test_strict_unexpected_pass") and event["phase"] == "call")
        self.assertEqual(event["outcome"], "xpassed")

    def test_skips_cannot_replace_controls(self):
        source = controls.SOURCE.replace('@pytest.mark.xfail(reason="known assertion failure", strict=True)',
                                         '@pytest.mark.skip(reason="omitted")')
        evidence = self.qualify(source)
        self.assertEqual(evidence["state"], "error")

    def test_missing_oracle_completion_cannot_certify_a_run(self):
        with self.assertRaisesRegex(ValueError, "oracle failed"):
            controls.validate([], {"error": "missing completion"})

    def test_native_report_cannot_lose_a_failure_even_with_nonzero_exit(self):
        evidence = self.qualify()
        result = controls.runner.Result(**copy.deepcopy(evidence["results"][0]["results"][0]))
        wrong = next(event for event in result.events if event["outcome"] == "failed")
        wrong["outcome"] = "passed"
        with self.assertRaisesRegex(ValueError, "lost, reordered or changed"):
            controls.validate([result], evidence["oracle"])

    def test_runtime_crash_is_not_an_expected_failure(self):
        evidence = self.qualify()
        result = controls.runner.Result(**evidence["results"][0]["results"][0])
        result.state = "execution-error"
        result.exit_code = -11
        with self.assertRaisesRegex(ValueError, "must complete"):
            controls.validate([result], evidence["oracle"])

    def test_bad_arguments_fail_before_execution(self):
        for arguments in (["--timeout", "nan"], ["--timeout", "0"],
                          ["--mode", "python", "--mode", "python"],
                          ["--input-seed", "-1"], ["--input-seed", "2147483648"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    controls.main(arguments)
                self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
