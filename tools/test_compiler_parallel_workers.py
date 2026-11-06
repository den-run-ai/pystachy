"""LLVM worker protocol and process-ownership controls; no LLVM installation needed."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bench/compiler_host/backend_workers.py"
SPEC = importlib.util.spec_from_file_location("backend_workers", SCRIPT)
workers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workers)

FAKE_LLVM = r'''
import json, os, pathlib, sys
args = sys.argv[1:]
tool = pathlib.Path(sys.argv[0]).name
if os.getenv("EVENTS"):
    with open(os.environ["EVENTS"], "a") as events:
        events.write(json.dumps({"tool": tool, "args": args, "cwd": os.getcwd()}) + "\n")
if os.getenv("FAIL_STAGE") == tool:
    print("deliberate LLVM failure", file=sys.stderr, flush=True)
    sys.exit(7)
output = pathlib.Path(args[args.index("-o") + 1])
if tool == "llvm-split":
    data = pathlib.Path(args[0]).read_bytes()
    for i in range(int(args[args.index("-j") + 1])):
        pathlib.Path(str(output) + str(i)).write_bytes(str(i).encode() + b":" + data)
else:
    inputs = [pathlib.Path(x) for x in args if x.endswith((".bc", ".o"))]
    inputs = [x for x in inputs if x != output]
    output.write_bytes(b"".join(x.read_bytes() for x in inputs))
'''

RUNNER = r'''
import importlib.util, json, os, pathlib, signal, subprocess, sys
spec = importlib.util.spec_from_file_location("workers", sys.argv[1])
workers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workers)
config = json.loads(pathlib.Path(sys.argv[2]).read_text())
scope = workers.Commands(owns_group=config.get("owns_group", True))
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


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pystachy-workers-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.llvm = self.root / "llvm"
        self.llvm.mkdir()
        for name in ("clang", "opt", "ld.lld", "llvm-split"):
            path = self.llvm / name
            path.write_text(f"#!{sys.executable}\n" + FAKE_LLVM)
            path.chmod(0o755)

    def job(self, name="job", opt=2):
        directory = self.root / name
        directory.mkdir()
        (directory / "input.bc").write_bytes(b"synthetic bitcode\n")
        job = {"version": 1, "input_sha256": workers.digest(directory / "input.bc"),
               "tool_sha256": workers.identity(self.llvm), "opt": opt, "emit": "object"}
        workers.write_json(directory / "job.json", job)
        return directory, job

    def test_result_binding_includes_input_and_output(self):
        directory, _ = self.job()
        workers.worker(directory, self.llvm)
        expected = workers.digest(directory / "job.json")
        self.assertTrue(workers.validate_result(directory, expected)["complete"])
        with self.assertRaisesRegex(RuntimeError, "job identity"):
            workers.validate_result(directory, "0" * 64)
        (directory / "output.o").write_bytes(b"altered")
        with self.assertRaisesRegex(RuntimeError, "altered worker output"):
            workers.validate_result(directory, expected)
        workers.worker(directory, self.llvm)
        (directory / "input.bc").write_bytes(b"altered after execution")
        with self.assertRaisesRegex(RuntimeError, "input changed"):
            workers.validate_result(directory, expected)

    def test_rejected_retry_cannot_reuse_stale_success(self):
        directory, _ = self.job()
        workers.worker(directory, self.llvm)
        (directory / "input.bc").write_bytes(b"invalid retry")
        with self.assertRaisesRegex(RuntimeError, "input/version"):
            workers.worker(directory, self.llvm)
        self.assertFalse((directory / "result.json").exists())
        self.assertFalse((directory / "output.o").exists())

    def test_detached_worker_needs_no_repository_imports(self):
        directory, _ = self.job()
        workers.worker(directory, self.llvm)
        expected = workers.digest(directory / "output.o")
        detached = self.root / "detached.py"
        detached.write_bytes(SCRIPT.read_bytes())
        result = subprocess.run([sys.executable, "-I", str(detached), "--worker", str(directory),
                                 "--llvm", str(self.llvm)], capture_output=True, text=True,
                                timeout=10, start_new_session=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(workers.digest(directory / "output.o"), expected)

    def test_failed_retry_leaves_incomplete_result(self):
        from unittest.mock import patch
        directory, _ = self.job()
        workers.worker(directory, self.llvm)
        with patch.dict(os.environ, FAIL_STAGE="opt"):
            with self.assertRaisesRegex(RuntimeError, "deliberate LLVM failure"):
                workers.worker(directory, self.llvm)
        result = json.loads((directory / "result.json").read_text())
        self.assertFalse(result["complete"])
        self.assertEqual(result["steps"][-1]["exit_code"], 7)
        self.assertFalse((directory / "output.o").exists())

    def test_opt_selection_and_deterministic_link_order(self):
        source = self.root / "source.bc"
        source.write_bytes(b"synthetic module\n")
        events = self.root / "events.jsonl"
        outputs = []
        for jobs in (1, 2):
            work, report = self.root / f"run-{jobs}", self.root / f"report-{jobs}.json"
            result = subprocess.run([sys.executable, str(SCRIPT), "--llvm", str(self.llvm),
                "--input", str(source), "--partitions", "4", "--jobs", str(jobs), "--opt", "0",
                "--work", str(work), "--report", str(report)], capture_output=True, text=True,
                env=dict(os.environ, EVENTS=str(events)), timeout=15, start_new_session=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(report.read_text())
            self.assertTrue(data["complete"])
            self.assertEqual(data["opt"], 0)
            self.assertEqual([r["partition"] for r in data["workers"]], list(range(4)))
            self.assertTrue(all(json.loads(p.read_text())["opt"] == 0 for p in work.glob("worker-*/job.json")))
            outputs.append((work / "compiler").read_bytes())
        self.assertEqual(outputs[0], outputs[1])
        invocations = [json.loads(line) for line in events.read_text().splitlines()]
        compilation = [row for row in invocations if row["tool"] == "clang" and "-c" in row["args"]]
        self.assertTrue(compilation)
        self.assertTrue(all("-O0" in row["args"] for row in compilation))


@unittest.skipUnless(os.name == "posix", "process groups need POSIX")
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


if __name__ == "__main__":
    unittest.main()
