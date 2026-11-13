"""Fail-closed controls for the optional emitted-LLVM validation probe.

Existing lint.yml test_*verif*.py discovery runs this file, including native
checks when the matching LLVM tools are installed. Alive2 and llubi are optional.
"""
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import llvm_validation as check


SUMMARY = """Summary:
  {} correct transformations
  {} incorrect transformations
  {} failed-to-prove transformations
  {} Alive2 errors
"""


class ResultTests(unittest.TestCase):
    def test_only_complete_success_is_a_refinement_result(self):
        result = check.alive_summary(SUMMARY.format(3, 0, 0, 0), 0, 3)
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["refinement_checked"])
        result = check.alive_summary(SUMMARY.format(2, 1, 0, 0), 0, 3)
        self.assertEqual(result["status"], "counterexample")
        self.assertFalse(result["refinement_checked"])

    def test_missing_unsupported_timeout_and_zero_counts_never_prove(self):
        for text, code, expected in (
            ("", 0, 3), ("Transformation seems to be correct!", 0, 3),
            ("ERROR: Unsupported instruction", 0, 3),
            (SUMMARY.format(3, 0, 0, 0), 1, 3),
            (SUMMARY.format(0, 0, 0, 0), 0, 3),
            (SUMMARY.format(0, 0, 0, 0), 0, 0),
            (SUMMARY.format(2, 0, 0, 0), 0, 3),
            (SUMMARY.format(4, 0, 0, 0), 0, 3),
            (SUMMARY.format(2, 0, 1, 0), 0, 3),
            (SUMMARY.format(2, 0, 0, 1), 0, 3),
            (SUMMARY.format(3, 0, 0, 0) * 2, 0, 3),
            (SUMMARY.format(3, 0, 0, 0) + "timeout", 0, 3),
            ("ERROR: Unsupported instruction\n" + SUMMARY.format(3, 0, 0, 0), 0, 3),
        ):
            with self.subTest(text=text, code=code, expected=expected):
                result = check.alive_summary(text, code, expected)
                self.assertEqual(result["status"], "inconclusive")
                self.assertFalse(result["refinement_checked"])

    def test_only_the_expected_poison_diagnostic_is_a_control_success(self):
        message = "UB triggered: Branch on poison\nExited with immediate UB.\n"
        self.assertTrue(check.poison_rejected({"status": "error", "returncode": 1}, message))
        for status, code, text in (
            ("ok", 0, message), ("timeout", None, message), ("unavailable", None, message),
            ("error", -9, message), ("error", 1, "unsupported instruction"),
            ("error", 1, "Exceed maximum steps"), ("error", 1, "parse error"),
            ("error", 1, "UB triggered: uninitialized load\nExited with immediate UB."),
            ("error", 1, message + "unsupported"),
        ):
            with self.subTest(status=status, code=code, text=text):
                self.assertFalse(check.poison_rejected({"status": status, "returncode": code}, text))

    def test_interpreter_driver_rejects_empty_or_missing_reference_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.ll"
            path.write_text("\n".join(f"define i64 @f.{name}() {{\n ret i64 0\n}}" for name in check.NAMES))
            for expected in ({}, {name: [] for name in check.NAMES}):
                with self.subTest(expected=expected), self.assertRaisesRegex(check.RunFailure, "incomplete"):
                    check.interpreter_module(path, expected)

    def test_count_and_function_mismatches_are_not_hidden_by_zip(self):
        expected = {"x": ["1", "2"]}
        for result in ({}, {"x": ["1"]}, {"x": ["1", "2", "3"]}, {"x": "12"}, []):
            with self.subTest(result=result), self.assertRaises(ValueError):
                check.compare(expected, result)
        self.assertEqual(check.compare(expected, expected), [])
        self.assertEqual(check.compare(expected, {"x": ["1", "3"]})[0]["case"], 1)

    def test_floats_distinguish_signed_zero_nan_and_finite_results(self):
        namespace = {}
        exec(check.SOURCE, namespace)
        good = check.outputs(namespace.__getitem__)
        self.assertIn("0000000000000000", good["affine"])
        self.assertIn("8000000000000000", good["affine"])
        self.assertIn("nan", good["affine"])
        bad = check.outputs(lambda name: (lambda a, b: math.nan) if name == "affine" else namespace[name])
        self.assertTrue(check.compare(good, bad))

    def test_missing_selected_function_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.ll"
            path.write_text("define void @other() {\n ret void\n}\n")
            with self.assertRaisesRegex(check.RunFailure, "expected.*f.masked_add"):
                check.selected_functions(path)

    def test_runner_distinguishes_unavailable_failure_and_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = check.Runner(Path(tmp), 10)
            missing, _, _ = runner.run("missing", [str(Path(tmp) / "missing")])
            runner.timeout = .05
            timeout, _, _ = runner.run("timeout", [sys.executable, "-c", "import time; time.sleep(5)"])
            runner.timeout = 10
            failure, _, _ = runner.run("error", [sys.executable, "-c", "raise SystemExit(7)"])
            self.assertEqual(missing["status"], "unavailable")
            self.assertEqual(timeout["status"], "timeout")
            self.assertEqual(failure["returncode"], 7)
            self.assertTrue(all((Path(tmp) / step["stderr"]).exists() for step in runner.steps))

    def test_invalid_pipeline_and_timeout_are_rejected_before_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            for pipeline in ("default<O2>", "mem2reg),globaldce,function(instcombine", "", "instcombine\n"):
                with self.subTest(pipeline=pipeline), self.assertRaises(ValueError):
                    check.probe(Path(tmp) / "unused", passes=pipeline)
            for timeout in (0, -1, math.nan, math.inf):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    check.probe(Path(tmp) / "unused", timeout=timeout)
            self.assertFalse((Path(tmp) / "unused").exists())

    def test_artifacts_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileExistsError):
            check.probe(tmp)


TOOLS = ("opt", "llvm-extract", "clang")


@unittest.skipUnless(sys.platform == "linux" and all(shutil.which(check.tool(t)) for t in TOOLS),
                     "Linux and matching LLVM tools required for real emitted-IR execution")
class NativeTests(unittest.TestCase):
    def test_real_lowering_boundaries_and_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "run"
            # A deliberately absent formal checker makes the test independent
            # of the host's optional tool installation, without claiming proof.
            report, code = check.probe(destination, alive_tv=str(Path(tmp) / "missing-alive-tv"))
            self.assertEqual(code, 2, report)
            self.assertEqual(report["status"], "inconclusive")
            self.assertFalse(report["refinement_checked"])
            self.assertEqual(report["alive2"]["status"], "unavailable")
            self.assertEqual(report["cases"], {"masked_add": 121, "signed_min": 121, "affine": 144})
            self.assertEqual(report["differential"]["before"]["status"], "matched")
            self.assertEqual(report["differential"]["after"]["status"], "matched")
            self.assertGreater(report["controls"]["wrong_mask"]["mismatches"], 0)
            self.assertEqual(report["controls"]["malformed_ir"]["status"], "detected")
            # (the lowering as emitted, before LLVM's passes: a sum under a 16-bit mask is one of
            # 32-bit values, gen_low32, where it was a checked 64-bit addition)
            before = (destination / "before.ll").read_text()
            self.assertIn(" = add i32 ", before)
            self.assertIn(" = and i32 ", before)
            self.assertNotIn("llvm.sadd.with.overflow.i64", before)
            self.assertEqual(json.loads((destination / "report.json").read_text()), json.loads(json.dumps(report)))
            self.assertTrue(report["compiler_sources"])
            for name, digest in report["artifacts"].items():
                self.assertEqual(check.fingerprint(destination / name), digest)

    def test_always_success_checker_fails_the_negative_control(self):
        # Protocol control, not an Alive2 validation claim. All real LLVM and
        # native steps execute, but this fake checker incorrectly accepts both.
        with tempfile.TemporaryDirectory() as tmp:
            checker = Path(tmp) / "fake-alive-tv"
            checker.write_text(f"#!{sys.executable}\nprint({SUMMARY.format(3, 0, 0, 0)!r})\n")
            checker.chmod(0o755)
            report, code = check.probe(Path(tmp) / "run", alive_tv=str(checker), require_alive=True)
            self.assertEqual(report["alive2"]["status"], "verified")
            self.assertEqual(report["controls"]["alive_wrong_mask"]["status"], "verified")
            self.assertEqual(code, 2)
            self.assertEqual(report["status"], "inconclusive")
            self.assertFalse(report["refinement_checked"])

    def test_optional_and_required_absent_checker_have_distinct_exit_codes(self):
        actual_which = shutil.which
        with tempfile.TemporaryDirectory() as tmp, patch.object(check.shutil, "which", side_effect=
                lambda name: None if name == "alive-tv" else actual_which(name)):
            for require, wanted_code in ((False, 0), (True, 2)):
                report, code = check.probe(Path(tmp) / str(require), require_alive=require)
                self.assertEqual(code, wanted_code)
                self.assertEqual(report["alive2"]["status"], "unavailable")
                self.assertFalse(report["refinement_checked"])

    def test_interpreter_always_success_and_unavailable_never_pass(self):
        actual_which = shutil.which
        with tempfile.TemporaryDirectory() as tmp, patch.object(check.shutil, "which", side_effect=
                lambda name: None if name == "alive-tv" else actual_which(name)):
            fake = Path(tmp) / "fake-llubi"
            fake.write_text(f"#!{sys.executable}\nimport sys\nif sys.argv[1] == '--version': print('fake llubi')\n")
            fake.chmod(0o755)
            for label, executable, status in (("missing", str(Path(tmp) / "missing-llubi"), "unavailable"),
                                              ("fake", str(fake), "inconclusive")):
                with self.subTest(label=label):
                    report, code = check.probe(Path(tmp) / label, llubi=executable)
                    self.assertEqual(code, 2)
                    self.assertEqual(report["llubi"]["status"], status)
                    self.assertEqual(report["status"], "inconclusive")
                    self.assertFalse(report["refinement_checked"])
                    self.assertEqual(report["differential"]["after"]["status"], "matched")

    @unittest.skipUnless(shutil.which("llubi"), "optional llubi is not installed")
    def test_real_llubi_checks_both_modules_and_detects_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, code = check.probe(Path(tmp) / "run", alive_tv=str(Path(tmp) / "missing-alive-tv"),
                                       llubi=shutil.which("llubi"))
            self.assertEqual(code, 2)  # Requested Alive2 is missing: never a proof.
            self.assertFalse(report["refinement_checked"])
            self.assertEqual(report["llubi"]["status"], "checked_paths", report)
            self.assertEqual(report["llubi"]["modules_checked"], 2)
            self.assertEqual(report["llubi"]["cases_per_module"], 386)
            self.assertEqual(report["llubi"]["controls"], {"wrong_mask": "detected", "overflow_poison": "detected"})

    def test_missing_required_llvm_tool_fails_without_native_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"PYSTACHY_LLVM": tmp}):
            report, code = check.probe(Path(tmp) / "run")
            self.assertEqual(code, 1)
            self.assertEqual(report["status"], "failed")
            self.assertFalse(report["refinement_checked"])
            self.assertNotIn("differential", report)
            self.assertEqual(report["steps"][-1]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
