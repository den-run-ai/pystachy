"""Fail-closed workload inventories and independently isolated suite execution."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
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

    def test_worker_cache_and_nested_jobs_override_caller(self):
        cache = self.work / "private-cache"
        with patch.dict(os.environ, PYSTACHY_CACHE="wrong", PYSTACHY_JOBS="99"):
            env = suites.environment(suites.SUITES[0], cache)
        self.assertEqual(env["PYSTACHY_CACHE"], str(cache))
        self.assertEqual(env["PYSTACHY_JOBS"], "1")

    def test_worker_limit_is_explicit_and_bounded(self):
        for jobs in ("0", "-1", "5", "1.5"):
            with self.subTest(jobs=jobs), redirect_stderr(io.StringIO()), \
                    patch.object(suites, "run") as run, self.assertRaises(SystemExit) as error:
                suites.main(["--jobs", jobs])
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_parallel_workers_keep_inventory_failure_and_private_caches(self):
        selected = tuple(suites.Suite(name, name) for name in ("one", "two", "three", "four"))
        modes = ["jit", "aot"]
        barrier = threading.Barrier(4)
        lock = threading.Lock()
        active, peak = 0, 0
        caches = {}

        def run(suite, mode, args):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                caches.setdefault(args.cache_dir, []).append((suite.name, mode))
            # Two rounds of four simultaneous tasks prove actual concurrency,
            # not just a worker-count option or sequentially mocked futures.
            barrier.wait(timeout=10)
            with lock:
                active -= 1
            with self.assertRaises(suites.runner.CollectionError):
                with suites.runner.lock_work_directory(self.args.work_dir):
                    self.fail("coordinator released its lock before workers completed")
            return {"suite": suite.name, "mode": mode, "state": "error" if suite.name == "one" else "passed",
                    "cases": 1}

        report = self.work / "parallel.json"
        with patch.object(suites, "SUITES", selected), patch.object(suites, "run", side_effect=run), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = suites.main(["--jobs", "4", "--work-dir", str(self.args.work_dir), "--json", str(report)])
        rows = json.loads(report.read_text())["suites"]
        self.assertEqual(code, 2)
        self.assertEqual(peak, 4)
        self.assertEqual(len(caches), 4)
        self.assertEqual(sorted(map(len, caches.values())), [2, 2, 2, 2])
        self.assertEqual([(row["suite"], row["mode"]) for row in rows],
                         [(suite.name, mode) for suite in selected for mode in modes])
        self.assertEqual([row["state"] for row in rows], ["error", "error"] + ["passed"] * 6)

    def test_interruption_kills_owned_children_and_stops_queued_suites(self):
        barrier = threading.Barrier(2)
        started = threading.Event()
        called = []
        exits = []
        selected = [suites.Suite(name, name) for name in ("running", "interrupt", "queued")]
        real_executor = suites.ThreadPoolExecutor

        class OrderedStartExecutor(real_executor):
            def submit(self, function, index):
                future = super().submit(function, index)
                if index == 0 and not started.wait(timeout=10):
                    raise RuntimeError("first worker did not enter its child process")
                return future

        def run(suite, mode, args):
            called.append(suite.name)
            if suite.name == "interrupt":
                barrier.wait(timeout=10)
                raise KeyboardInterrupt()
            @contextmanager
            def scope(process):
                with args.process_scope(process):
                    # Force the first submitted future to remain blocked while
                    # a later future interrupts. Submission-order result reads
                    # would hide cancellation until this child's timeout.
                    started.set()
                    barrier.wait(timeout=10)
                    yield

            result = suites.run_process("running", [sys.executable, "-c", "import time; time.sleep(60)"],
                                        os.environ.copy(), suites.ROOT, status=None, timeout=10,
                                        process_scope=scope)
            exits.append(result.returncode)
            return {"suite": suite.name, "mode": mode, "state": "passed", "cases": 1}

        previous = signal.getsignal(signal.SIGTERM)
        args = SimpleNamespace(**vars(self.args), jobs=2)
        with patch.object(suites, "run", side_effect=run), \
                patch.object(suites, "ThreadPoolExecutor", OrderedStartExecutor), \
                self.assertRaises(KeyboardInterrupt):
            suites.run_selected(selected, ["python"], args)
        self.assertEqual(set(called), {"interrupt", "running"})
        self.assertEqual(exits, [-signal.SIGKILL])
        self.assertIs(signal.getsignal(signal.SIGTERM), previous)

    def test_cancellation_kills_descendant_after_its_group_leader_exits(self):
        processes = suites.WorkerProcesses()
        parent = ("import subprocess, sys; "
                  "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])")

        @contextmanager
        def scope(process):
            with processes.scope(process):
                self.assertEqual(process.wait(timeout=10), 0)
                # A completed leader does not mean its inherited pipes have
                # closed. Cancellation must still kill the live descendant.
                processes.cancel()
                yield

        result = suites.run_process("orphan", [sys.executable, "-c", parent], os.environ.copy(),
                                    suites.ROOT, status=None, timeout=2, process_scope=scope)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertFalse(processes.processes)

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
        (suites.ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=suites.ROOT / "build", prefix="suite-isolation-") as temporary:
            root = Path(temporary)
            selected = []
            for name, value in (("first", 1), ("second", 2)):
                path = root / name
                path.mkdir()
                (path / "helper.py").write_text(f"VALUE = {value}\n")
                (path / "test_value.py").write_text(f"import helper\ndef test_value(): assert helper.VALUE == {value}\n")
                selected.append(suites.Suite(name, path.relative_to(suites.ROOT).as_posix()))
            args = SimpleNamespace(**vars(self.args), jobs=2)
            rows = suites.run_selected(selected, ["python"], args)
            for row in rows:
                self.assertEqual(row["state"], "passed", row)
                self.assertEqual(row["cases"], 1)

    def test_real_parallel_failure_cannot_hide_other_suites(self):
        (suites.ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=suites.ROOT / "build", prefix="suite-failure-") as temporary:
            root = Path(temporary)
            selected = []
            for name, assertion in (("bad", "False"), ("good", "True")):
                path = root / name
                path.mkdir()
                (path / "test_case.py").write_text(f"def test_case(): assert {assertion}\n")
                selected.append(suites.Suite(name, path.relative_to(suites.ROOT).as_posix()))
            report = self.work / "failure.json"
            with patch.object(suites, "SUITES", selected), redirect_stdout(io.StringIO()), \
                    redirect_stderr(io.StringIO()):
                code = suites.main(["--mode", "python", "--jobs", "2", "--work-dir",
                                    str(self.args.work_dir), "--json", str(report)])
            evidence = json.loads(report.read_text())
            self.assertEqual(code, 2)
            self.assertEqual(evidence["exit_code"], 2)
            self.assertEqual([row["state"] for row in evidence["suites"]], ["error", "passed"])
            self.assertEqual(evidence["suites"][0]["evidence"]["results"][0]["state"], "test-failed")


if __name__ == "__main__":
    unittest.main()
