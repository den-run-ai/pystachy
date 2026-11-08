"""Local admission, application reporting and process-ownership controls."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import application_workers as application
import process_workers as workers


TOOLS = Path(__file__).resolve().parent
SCRIPT = TOOLS / "process_workers.py"

RUNNER = r'''
import importlib.util, json, os, pathlib, signal, subprocess, sys
spec = importlib.util.spec_from_file_location("workers", sys.argv[1])
workers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workers)
config = json.loads(pathlib.Path(sys.argv[2]).read_text())
scope = workers.Commands(owns_group=config.get("owns_group", True),
                         output_limit_bytes=config.get("output_limit_bytes", 1024 * 1024))
report = {"complete": False}
try:
    with scope:
        report["pid"], report["pgid"] = os.getpid(), os.getpgrp()
        if config.get("launch_signal"):
            original = subprocess.Popen
            def launch(*args, **kwargs):
                proc = original(*args, **kwargs)
                os.kill(os.getpid(), signal.SIGTERM)
                return proc
            workers.subprocess.Popen = launch
        for result in scope.run(config["commands"], dict(os.environ), config["timeout"],
                                jobs=config.get("jobs", 1)):
            if result["exit_code"]:
                raise RuntimeError("command failed")
        report["complete"] = True
except (OSError, RuntimeError) as error:
    report["error"] = str(error)
finally:
    report["results"] = scope.results
    pathlib.Path(sys.argv[3]).write_text(json.dumps(report))
sys.exit(0 if report["complete"] else 1)
'''

BLOCK = r'''
import os, pathlib, signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, "-c",
    "import os, pathlib, signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); print('grandchild ready', flush=True); time.sleep(30)",
    sys.argv[1] + ".child"])
pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))
print("worker ready", flush=True)
print("worker stderr", file=sys.stderr, flush=True)
while not pathlib.Path(sys.argv[1] + ".child").exists():
    time.sleep(.005)
pathlib.Path(sys.argv[1] + ".ready").write_text(str(os.getpgrp()))
time.sleep(30)
'''


def living(pid):
    """Check our namespace without mistaking an unreaped zombie for live work."""
    if Path("/proc/self/status").exists():
        namespace = os.readlink("/proc/self/ns/pid")
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if os.readlink(entry / "ns/pid") != namespace:
                    continue
                status = (entry / "status").read_text().splitlines()
                ids = next(line.split()[1:] for line in status if line.startswith("NSpid:"))
                state = next(line.split()[1] for line in status if line.startswith("State:"))
                if int(ids[-1]) == pid and state != "Z":
                    return True
            except (OSError, StopIteration, ValueError):
                pass
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class ResourceTests(unittest.TestCase):
    def job(self, key, resources=None, source="print('done')"):
        return workers.Job(key, [sys.executable, "-c", source], resources)

    def test_worker_and_deadline_limits_reject_before_spawn(self):
        options = ({"jobs": 0}, {"jobs": 3}, {"jobs": True}, {"timeout": 0},
                   {"timeout": 901}, {"timeout": float("inf")}, {"timeout": float("nan")})
        for option in options:
            with self.subTest(option=option), workers.Commands(owns_group=False) as scope, \
                    patch.object(scope, "start") as start, self.assertRaises(ValueError):
                list(scope.run([self.job("unstarted")], dict(os.environ), **option))
            start.assert_not_called()
        with workers.Commands(owns_group=False) as scope:
            self.assertEqual(list(scope.run([], dict(os.environ), timeout=900, jobs=2)), [])
        with self.assertRaises(ValueError):
            workers.Budget(cpu=3, memory_bytes=0, input_bytes=0)

    def test_default_budget_and_output_limit_cannot_be_disabled(self):
        for limit in (None, 0, -1, float("inf"), True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                workers.Commands(output_limit_bytes=limit)
        with workers.Commands(owns_group=False) as scope, patch.object(scope, "start") as start, \
                self.assertRaisesRegex(ValueError, "resource budget"):
            list(scope.run([self.job("oversized", workers.Resources(cpu=3))], dict(os.environ), jobs=2))
        start.assert_not_called()

    def test_cpu_memory_and_input_reservations_each_bound_live_jobs(self):
        cases = (
            workers.Resources(cpu=2, memory_bytes=1, input_bytes=1),
            workers.Resources(cpu=1, memory_bytes=6, input_bytes=1),
            workers.Resources(cpu=1, memory_bytes=1, input_bytes=6),
        )
        budget = workers.Budget(cpu=2, memory_bytes=8, input_bytes=8)
        for request in cases:
            with self.subTest(request=request.as_dict()), workers.Commands(owns_group=False) as scope:
                jobs = [self.job(index, request) for index in range(3)]
                results = list(scope.run(jobs, dict(os.environ), timeout=5, jobs=2, budget=budget))
                self.assertEqual([row["key"] for row in results], [0, 1, 2])
                self.assertTrue(all(row["exit_code"] == 0 for row in results))
                self.assertEqual(scope.peak_reserved, request.as_dict())
                for previous, current in zip(results, results[1:]):
                    self.assertLessEqual(previous["finished_monotonic_s"], current["started_monotonic_s"])

    def test_oversized_or_unqueueable_jobs_are_rejected_before_spawn(self):
        requests = (workers.Resources(cpu=3), workers.Resources(memory_bytes=9),
                    workers.Resources(input_bytes=9), workers.Resources(input_bytes=5))
        budget = workers.Budget(cpu=2, memory_bytes=8, input_bytes=8, queued_bytes=4)
        for request in requests:
            with self.subTest(request=request.as_dict()), workers.Commands(owns_group=False) as scope, \
                    patch.object(scope, "start") as start, self.assertRaises(ValueError):
                list(scope.run([self.job("oversized", request)], dict(os.environ), timeout=5, jobs=2, budget=budget))
            start.assert_not_called()

    def test_queue_consumption_is_lazy_with_one_waiting_descriptor(self):
        consumed = []

        def jobs():
            for index in range(100):
                consumed.append(index)
                yield self.job(index, workers.Resources(input_bytes=4))

        with workers.Commands(owns_group=False) as scope:
            results = scope.run(jobs(), dict(os.environ), timeout=5, jobs=2,
                                budget=workers.Budget(cpu=1, memory_bytes=0, input_bytes=4, queued_bytes=4))
            self.assertEqual(next(results)["key"], 0)
            self.assertEqual(consumed, [0, 1])
            results.close()
        self.assertEqual([row["key"] for row in scope.results], [0])

    def test_captures_are_bounded_but_normal_output_hashes_remain_complete(self):
        output, error = b"x" * 5000, b"e" * 2000
        job = self.job("output", source="import os; os.write(1, b'x'*5000); os.write(2, b'e'*2000)")
        with workers.Commands(owns_group=False, capture_bytes=37) as scope:
            result = next(scope.run([job], dict(os.environ), timeout=5))
        self.assertEqual(result["stdout"], "x" * 37)
        self.assertEqual(result["stderr"], "e" * 37)
        for name, data in (("stdout", output), ("stderr", error)):
            self.assertEqual(result[name + "_bytes"], len(data))
            self.assertEqual(result[name + "_hashed_bytes"], len(data))
            self.assertEqual(result[name + "_sha256"], hashlib.sha256(data).hexdigest())
            self.assertIsNone(result[name + "_prefix_sha256"])
            self.assertTrue(result[name + "_truncated"])

    def test_sparse_oversized_output_cannot_force_unbounded_cleanup_reads(self):
        original = tempfile.TemporaryFile
        streams = []

        class TrackedStream:
            def __init__(self):
                self.stream, self.bytes_read = original(), 0
                streams.append(self)

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def read(self, count=-1):
                value = self.stream.read(count)
                self.bytes_read += len(value)
                return value

        job = self.job("sparse", source="import os; os.ftruncate(1, 8*1024*1024)")
        scope = workers.Commands(owns_group=False, capture_bytes=128, output_limit_bytes=1024)
        with patch.object(workers.tempfile, "TemporaryFile", side_effect=TrackedStream), \
                self.assertRaisesRegex(RuntimeError, "output byte limit"), scope:
            list(scope.run([job], dict(os.environ), timeout=5))
        self.assertLessEqual(sum(stream.bytes_read for stream in streams), 1024)
        self.assertEqual(len(scope.results), 1)
        result = scope.results[0]
        self.assertTrue(result["output_limit_exceeded"])
        self.assertEqual(result["stdout_bytes"], 8 * 1024 * 1024)
        self.assertEqual(result["stdout_hashed_bytes"], 1024)
        self.assertIsNone(result["stdout_sha256"])
        self.assertEqual(result["stdout_prefix_sha256"], hashlib.sha256(b"\0" * 1024).hexdigest())
        self.assertEqual(len(result["stdout"]), 128)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pystachy-worker-ownership-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runner = self.root / "runner.py"
        self.runner.write_text(RUNNER)

    def command(self, source, *args):
        return [sys.executable, "-c", source, *map(str, args)]

    def launch(self, commands, **options):
        config, report = self.root / "config.json", self.root / "report.json"
        config.write_text(json.dumps(dict(commands=commands, timeout=options.pop("timeout", 5), **options)))
        proc = subprocess.Popen([sys.executable, str(self.runner), str(SCRIPT), str(config), str(report)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.addCleanup(self.kill, proc)
        return proc, report

    @staticmethod
    def kill(proc):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()

    def wait_file(self, path, proc):
        deadline = time.monotonic() + 5
        while not path.exists():
            if proc.poll() is not None or time.monotonic() >= deadline:
                self.fail(f"worker did not publish {path.name}")
            time.sleep(.01)

    def collect(self, proc, report):
        out, err = proc.communicate(timeout=8)
        self.assertEqual(proc.returncode, 1, (out, err))
        self.assertTrue(report.exists(), err)
        data = json.loads(report.read_text())
        self.assertFalse(data["complete"])
        return data

    def assert_dead(self, path):
        for name in (path, Path(str(path) + ".child")):
            if name.exists():
                pid = int(name.read_text())
                deadline = time.monotonic() + 2
                while living(pid) and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertFalse(living(pid), f"process {pid} survived cleanup")

    def test_failure_stops_queued_work_and_stubborn_descendants(self):
        pid, queued = self.root / "blocking", self.root / "queued"
        failure = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(.005)\nsys.exit(7)"
        commands = [("blocking", self.command(BLOCK, pid)),
                    ("failure", self.command(failure, str(pid) + ".ready")),
                    ("queued", self.command("import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", queued))]
        proc, report = self.launch(commands, jobs=2)
        data = self.collect(proc, report)
        self.assertFalse(queued.exists())
        self.assertEqual({r["key"] for r in data["results"]}, {"blocking", "failure"})
        blocking = next(r for r in data["results"] if r["key"] == "blocking")
        self.assertTrue(blocking["cancelled"])
        self.assertIn("worker stderr", blocking["stderr"])
        self.assert_dead(pid)

    def test_timeout_preserves_logs_and_reaps_tree(self):
        pid = self.root / "timeout"
        proc, report = self.launch([("timeout", self.command(BLOCK, pid))], timeout=.3)
        data = self.collect(proc, report)
        self.assertIn("exceeded", data["error"])
        self.assertTrue(data["results"][0]["timed_out"])
        self.assertIn("worker ready", data["results"][0]["stdout"])
        self.assert_dead(pid)

    def test_signal_cancels_owned_tree(self):
        pid = self.root / "signal"
        proc, report = self.launch([("signal", self.command(BLOCK, pid))])
        self.wait_file(Path(str(pid) + ".ready"), proc)
        self.assertEqual(int(Path(str(pid) + ".ready").read_text()), proc.pid)
        self.assertTrue(living(int(pid.read_text())))
        self.assertTrue(living(int(Path(str(pid) + ".child").read_text())))
        proc.send_signal(signal.SIGTERM)
        data = self.collect(proc, report)
        self.assertIn("signal 15", data["error"])
        self.assert_dead(pid)

    def test_signal_during_popen_is_owned(self):
        proc, report = self.launch([("launch", self.command("import time; time.sleep(30)"))], launch_signal=True)
        data = self.collect(proc, report)
        self.assertEqual(len(data["results"]), 1)
        self.assertTrue(data["results"][0]["cancelled"])
        self.assertLess(data["results"][0]["exit_code"], 0)

    def test_spawn_failure_never_starts_queued_work(self):
        queued = self.root / "queued"
        commands = [("missing", [str(self.root / "missing-executable")]),
                    ("queued", self.command("import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", queued))]
        proc, report = self.launch(commands, jobs=2)
        data = self.collect(proc, report)
        self.assertEqual(data["results"], [])
        self.assertFalse(queued.exists())

    def test_live_output_limit_cancels_siblings_before_queued_work(self):
        pid, queued = self.root / "blocking", self.root / "queued"
        overflow = ("import os,pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\n"
                    "while not p.exists(): time.sleep(.005)\n"
                    "os.ftruncate(1, 8192); time.sleep(30)")
        commands = [("blocking", self.command(BLOCK, pid)),
                    ("overflow", self.command(overflow, str(pid) + ".ready")),
                    ("queued", self.command("import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", queued))]
        proc, report = self.launch(commands, jobs=2, output_limit_bytes=1024)
        data = self.collect(proc, report)
        self.assertIn("output byte limit", data["error"])
        self.assertEqual({r["key"] for r in data["results"]}, {"blocking", "overflow"})
        overflow_result = next(row for row in data["results"] if row["key"] == "overflow")
        self.assertTrue(overflow_result["output_limit_exceeded"])
        self.assertLessEqual(overflow_result["stdout_hashed_bytes"] + overflow_result["stderr_hashed_bytes"], 1024)
        self.assertFalse(queued.exists())
        self.assert_dead(pid)

    def test_nested_controller_stays_in_outer_group(self):
        pid = self.root / "nested"
        inner_config = self.root / "inner-config.json"
        inner_report = self.root / "inner-report.json"
        inner_config.write_text(json.dumps({"commands": [("inner", self.command(BLOCK, pid))],
                                            "timeout": 20, "owns_group": False}))
        command = [sys.executable, str(self.runner), str(SCRIPT), str(inner_config), str(inner_report)]
        proc, report = self.launch([("outer", command)], timeout=20)
        self.wait_file(Path(str(pid) + ".ready"), proc)
        self.assertEqual(int(Path(str(pid) + ".ready").read_text()), proc.pid)
        os.killpg(proc.pid, signal.SIGTERM)
        self.collect(proc, report)
        self.assert_dead(pid)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pystachy-application-workers-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest, self.report = self.root / "jobs.json", self.root / "report.json"

    def job(self, key, source, *arguments, **options):
        return {"key": key, "argv": [sys.executable, "-c", source, *map(str, arguments)],
                "memory_bytes": 1024 * 1024, **options}

    def write(self, jobs):
        self.manifest.write_text(json.dumps({"version": 1, "jobs": jobs}))

    def invoke(self, report=None, options=()):
        command = [sys.executable, str(TOOLS / "application_workers.py"), str(self.manifest),
                   "--report", str(report or self.report), "--jobs", "2", "--cpus", "2", "--memory-mib", "64",
                   "--input-mib", "1", "--queued-input-mib", "1", "--timeout", "3", *options]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)

        def cleanup():
            try:
                os.killpg(process.pid, workers.signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

        # Keep fallback cleanup after assertions; doing it on normal return
        # would hide an application controller that left grandchildren alive.
        self.addCleanup(cleanup)
        try:
            output, error = process.communicate(timeout=10)
        except BaseException:
            cleanup()
            raise
        return subprocess.CompletedProcess(command, process.returncode, output, error)

    def test_stdin_nested_thread_caps_and_submission_order(self):
        (self.root / "input.txt").write_text("batch data\n")
        self.write([
            self.job("first", "import os,sys,time; time.sleep(.03); print(sys.stdin.read().strip(), os.environ['OMP_NUM_THREADS'])",
                     stdin="input.txt", input_bytes=11, env={"OMP_NUM_THREADS": "99"}),
            self.job("second", "print('second')"),
        ])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertTrue(report["complete"])
        self.assertEqual([row["key"] for row in report["results"]], ["first", "second"])
        self.assertEqual([row["stdout"] for row in report["results"]], ["batch data 1\n", "second\n"])
        self.assertLessEqual(report["peak_reserved"]["cpu"], 2)
        self.assertEqual(report["peak_reserved"]["input_bytes"], 11)

    def test_stdin_reservation_failure_does_not_spawn_work(self):
        (self.root / "input.txt").write_text("batch data\n")
        self.write([self.job("too-large", "print('must not run')", stdin="input.txt", input_bytes=1)])
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(report["results"], [])
        self.assertIn("stdin artifact exceeds", report["error"])

    def test_cli_limits_do_not_start_work(self):
        marker = self.root / "started"
        self.write([self.job("unstarted", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", marker)])
        for option, value in (("--jobs", "3"), ("--cpus", "3"), ("--timeout", "901"),
                              ("--timeout", "nan"), ("--output-limit-mib", "0")):
            with self.subTest(option=option, value=value):
                result = self.invoke(options=(option, value))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())

    def test_failed_report_publication_preserves_old_report_and_removes_temporary(self):
        previous = {"version": 1, "complete": False}
        application.atomic_json(self.report, previous)
        with patch.object(application.os, "replace", side_effect=OSError("publish failed")), \
                self.assertRaises(OSError):
            application.atomic_json(self.report, {"version": 1, "complete": True})
        self.assertEqual(json.loads(self.report.read_bytes()), previous)
        self.assertEqual(list(self.root.glob("report.json.*")), [])

    def test_failure_cancels_children_and_never_starts_queued_job(self):
        marker, queued = self.root / "blocking.pid", self.root / "queued"
        failure = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(.005)\nsys.exit(7)"
        self.write([
            self.job("blocking", BLOCK, marker),
            self.job("failure", failure, str(marker) + ".ready"),
            self.job("queued", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", queued),
        ])
        result = self.invoke()
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertEqual([row["key"] for row in report["results"]], ["blocking", "failure"])
        self.assertTrue(report["results"][0]["cancelled"])
        self.assertEqual(report["results"][1]["exit_code"], 7)
        self.assertFalse(queued.exists())
        for path in (marker, Path(str(marker) + ".child")):
            self.assertFalse(living(int(path.read_text())))

    def test_bad_path_and_environment_types_are_validation_errors(self):
        for values in ({"stdin": 1}, {"stdin": []}, {"cwd": 1}, {"env": {"": "invalid"}}):
            self.write([self.job("invalid", "print('unused')", **values)])
            with self.subTest(values=values), self.assertRaises(ValueError):
                list(application.read_jobs(self.manifest))

    def test_path_lookup_cannot_hide_report_executable_collision(self):
        directory = self.root / "bin"
        directory.mkdir()
        executable = directory / "worker"
        original = b"#!/bin/sh\nexit 0\n"
        executable.write_bytes(original)
        executable.chmod(0o755)
        self.manifest.write_text(json.dumps({"version": 1, "jobs": [{
            "key": "worker", "argv": ["worker"], "env": {"PATH": str(directory)}}]}))
        with self.assertRaisesRegex(ValueError, "absolute executable"):
            list(application.read_jobs(self.manifest))
        result = self.invoke(report=executable)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute executable", result.stderr)
        self.assertEqual(executable.read_bytes(), original)

    def test_reports_cannot_replace_the_manifest_or_stdin_artifact(self):
        source = self.root / "input.txt"
        source.write_text("source must survive\n")
        self.write([self.job("valid", "pass", stdin="input.txt", input_bytes=20)])
        for target in (self.manifest, source):
            previous = target.read_bytes()
            with self.subTest(target=target.name):
                result = self.invoke(report=target)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_bytes(), previous)



if __name__ == "__main__":
    unittest.main()
