"""Fail-closed workload inventories and independently isolated suite execution."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pytest_native_suites as suites


class WorkloadSuites(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.args = SimpleNamespace(work_dir=self.work / "runs", compiler="unused",
                                    python=sys.executable, timeout=10)

    def test_registry_is_unique_and_paths_stay_in_repository(self):
        names = [suite.name for suite in suites.SUITES]
        self.assertEqual(len(names), len(set(names)))
        for suite in suites.SUITES:
            for path in (suite.path, *suite.imports):
                self.assertTrue((suites.ROOT / path).resolve().is_relative_to(suites.ROOT))
        with self.assertRaises(ValueError):
            suites.select([names[0], names[0]], "all")
        with self.assertRaises(ValueError):
            suites.select(["missing"], "all")
        with self.assertRaises(ValueError):
            suites.select(["pyperformance-json"], "examples")

    def test_all_benchmark_modules_are_registered_once(self):
        selected = suites.select(None, "pyperformance")
        expected = sorted((suites.ROOT / "bench/pyperformance/pytest").glob("test_*.py"))
        self.assertEqual(sorted(suites.ROOT / suite.path for suite in selected), expected)
        self.assertEqual(len(set(suite.path for suite in selected)), len(expected))

    def test_caller_paths_and_optimized_assertions_cannot_change_reference(self):
        suite = suites.Suite("sample", "examples/sample", ("ports",))
        with patch.dict(os.environ, PYTHONPATH="wrong", PYSTACHY_PATH="wrong", PYTHONOPTIMIZE="1"):
            env = suites.environment(suite)
        self.assertEqual(env["PYTHONPATH"], str(suites.ROOT / "ports"))
        self.assertEqual(env["PYSTACHY_PATH"], env["PYTHONPATH"])
        self.assertNotIn("PYTHONOPTIMIZE", env)

    def test_zero_exit_without_report_cannot_reuse_old_evidence(self):
        suite = suites.Suite("sample", "examples/sample")
        source = suites.ROOT / "examples/sample/test_one.py"
        report = self.args.work_dir / "sample/python/result.json"
        report.parent.mkdir(parents=True)
        report.write_text('{"exit_code":0}')
        with patch.object(suites.runner, "discover", return_value=[source]), \
                patch.object(Path, "read_text", return_value="def test_one(): pass"), \
                patch.object(suites, "run_process", return_value=subprocess.CompletedProcess([], 0, b"", b"")):
            row = suites.run(suite, "python", self.args)
        self.assertEqual(row["state"], "error")
        self.assertFalse(report.exists())

    def test_empty_suite_fails_before_any_subprocess(self):
        with patch.object(suites.runner, "discover", return_value=[]), \
                patch.object(suites, "run_process") as process:
            row = suites.run(suites.Suite("empty", "examples/empty"), "python", self.args)
        self.assertEqual(row["state"], "error")
        process.assert_not_called()

    def test_all_requested_suites_report_even_after_failure(self):
        results = [{"suite": "first", "mode": "python", "state": "error", "cases": 0},
                   {"suite": "second", "mode": "python", "state": "passed", "cases": 1}]
        report = self.work / "summary.json"
        with patch.object(suites, "SUITES", (suites.Suite("first", "a"), suites.Suite("second", "b"))), \
                patch.object(suites, "run", side_effect=results), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = suites.main(["--mode", "python", "--work-dir", str(self.args.work_dir), "--json", str(report)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(report.read_text())["suites"], results)

    def test_skipped_case_cannot_count_as_qualified_workload(self):
        case = "test_sample.py::test_one"
        events = [{"nodeid": case, "phase": "setup", "outcome": "skipped", "detail": "reason"},
                  {"nodeid": case, "phase": "teardown", "outcome": "passed", "detail": ""}]
        result = suites.runner.Result("test_sample.py", cases=[case], events=events, state="passed", exit_code=0)
        from dataclasses import asdict
        evidence = {"mode": "python", "root": str(suites.ROOT), "exit_code": 0,
                    "results": [asdict(result)], "differences": [],
                    "oracle": {"cases": [case], "events": events, "exit_code": 0}}
        with self.assertRaisesRegex(ValueError, "execute and pass"):
            suites.validate(evidence, [case], ["test_sample.py"], "python", 0)

    def test_passing_call_cannot_hide_skipped_or_xfailed_cleanup(self):
        case = "test_sample.py::test_one"
        from dataclasses import asdict
        for outcome in ("skipped", "xfailed"):
            events = [{"nodeid": case, "phase": phase, "outcome": "passed", "detail": ""}
                      for phase in ("setup", "call", "teardown")]
            events[-1]["outcome"] = outcome
            result = suites.runner.Result("test_sample.py", cases=[case], events=events, state="passed", exit_code=0)
            evidence = {"mode": "python", "root": str(suites.ROOT), "exit_code": 0,
                        "results": [asdict(result)], "differences": [],
                        "oracle": {"cases": [case], "events": events, "exit_code": 0}}
            with self.subTest(outcome=outcome), self.assertRaisesRegex(ValueError, "case and phase"):
                suites.validate(evidence, [case], ["test_sample.py"], "python", 0)

    def test_sibling_imports_remain_independent_and_compare_with_pytest(self):
        # Use real runner subprocesses with the repository's tool paths, but
        # temporary per-suite sources under the repository's ignored build tree.
        with tempfile.TemporaryDirectory(dir=suites.ROOT / "build", prefix="suite-isolation-") as temporary:
            root = Path(temporary)
            selected = []
            for name, value in (("first", 1), ("second", 2)):
                path = root / name
                path.mkdir()
                (path / "helper.py").write_text(f"VALUE = {value}\n")
                (path / "test_value.py").write_text(f"import helper\ndef test_value(): assert helper.VALUE == {value}\n")
                selected.append(suites.Suite(name, path.relative_to(suites.ROOT).as_posix()))
            for suite in selected:
                row = suites.run(suite, "python", self.args)
                self.assertEqual(row["state"], "passed", row)
                self.assertEqual(row["cases"], 1)


if __name__ == "__main__":
    unittest.main()
