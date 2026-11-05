"""Process-isolated runtime builds: budgets, rendezvous, diagnostics and drain.

The rendezvous uses pipe gates: both jobs must announce readiness while neither
can finish. Deadlines are deadlock watchdogs, never speedup assertions. The
serial negative control releases each gate in turn and cannot obtain the same
witness. No LLVM build is needed for this suite.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import diagnostics, driver

ROOT = Path(__file__).resolve().parents[1]


class BuildBudget(unittest.TestCase):
    def test_default_and_supported_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(driver.build_jobs(), 1)
            self.assertEqual(driver.lto_partitions(1), 0)
        for value in ("1", "2", "4", "64"):
            with self.subTest(value=value), patch.dict(os.environ, PYSTACHY_BUILD_JOBS=value):
                self.assertEqual(driver.build_jobs(), int(value))

    def test_invalid_budget_is_a_diagnostic(self):
        for value in ("", "0", "65", "128", "-1", "+2", "1.5", "two", " 2", "2\n", "²"):
            with self.subTest(value=value), patch.dict(os.environ, PYSTACHY_BUILD_JOBS=value):
                with contextlib.redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit) as caught:
                    driver.build_jobs()
                self.assertEqual(caught.exception.code, 1)
                self.assertIn("PYSTACHY_BUILD_JOBS must be an integer from 1 to 64", output.getvalue())

    def test_lto_shares_the_driver_budget(self):
        with patch.object(driver, "PLATFORM", "linux"):
            for jobs, partitions in ((1, 1), (2, 2), (4, 4), (64, 64)):
                with self.subTest(jobs=jobs), patch.dict(os.environ, PYSTACHY_LTO_PARTITIONS=str(partitions)):
                    self.assertEqual(driver.lto_partitions(jobs), partitions)
            for value in ("2", "65", "", "-1", "x", "²"):
                with self.subTest(value=value), patch.dict(os.environ, PYSTACHY_LTO_PARTITIONS=value):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        driver.lto_partitions(1)

    def test_lto_platform_limit_is_explicit(self):
        with patch.object(driver, "PLATFORM", "darwin"), patch.dict(os.environ, PYSTACHY_LTO_PARTITIONS="1"):
            with contextlib.redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit):
                driver.lto_partitions(1)
            self.assertIn("requires Linux and LLVM 18 LLD", output.getvalue())

    def test_child_reuses_hosted_interpreter_and_native_compiler(self):
        compiler = "/compiler dir/owner's $compiler.py"
        interpreter = "/venv dir/owner's python"
        with patch.object(sys, "executable", interpreter):
            self.assertEqual(shlex.split(driver.compiler_command(compiler)), [interpreter, compiler])
        with patch.object(sys, "implementation", SimpleNamespace(name="pystachy")):
            with tempfile.TemporaryDirectory(prefix="compiler dir ' $; ") as folder:
                native = Path(folder) / "pystachy"
                native.write_text("#!/bin/sh\nexit 0\n")
                native.chmod(0o700)
                self.assertEqual(shlex.split(driver.compiler_command(str(native))), [str(native)])
                native.chmod(0o600)
                self.assertEqual(driver.compiler_command(str(native)), "")
                source = Path(folder) / "compiler.pys"
                source.write_text("print(42)\n")
                self.assertEqual(driver.compiler_command(str(source)), "")
                self.assertEqual(driver.compiler_command(compiler), "")


WORKER = r'''import json, os, sys
from pathlib import Path
name, directory, gate, events, status, message = sys.argv[1:]
root = Path(directory)
other = "second" if name == "first" else "first"
def event(phase):
    data = dict(phase=phase, name=name, pid=os.getpid(), parent=os.getppid(),
                other_done=(root / (other + ".done")).exists())
    os.write(int(events), (json.dumps(data) + "\n").encode())
print(message, file=sys.stderr, flush=True)
event("ready")
if os.read(int(gate), 1) != b"x":
    raise SystemExit(97)
(root / (name + ".done")).touch()
event("done")
raise SystemExit(int(status))
'''

LAUNCH = '''import json, os, sys
sys.path.insert(0, sys.argv[1])
from src.pystachy_compiler import driver
first, second, directory, mode = sys.argv[2:]
if mode == "serial":
    status = driver.sh("( " + first + " ); x=$?; ( " + second + ' ); y=$?; [ "$x" -eq 0 ] || exit "$x"; exit "$y"')
elif mode == "primary":
    status = driver.parallel_commands(first, second, directory, True)
else:
    status = driver.parallel_commands(first, second, directory)
with open(directory + "/joined.json", "w") as stream:
    json.dump([os.path.exists(directory + "/" + name + ".done") for name in ("first", "second")], stream)
raise SystemExit(status)
'''


@unittest.skipUnless(os.name == "posix", "the compiler's process driver requires POSIX")
class RuntimeProcesses(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pystachy parallel ' $; ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.worker = self.root / "worker ' ; $.py"
        self.worker.write_text(WORKER)
        self.pending = []
        self.buffer = b""
        self.handles = []
        self.process = None
        self.addCleanup(self.stop)

    def stop(self):
        if self.process is not None:
            # Also handles a broken implementation that returns without joining
            # one of its jobs; a test must never leak its deliberate pipe waiters.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.communicate(timeout=5)
        for handle in self.handles:
            try:
                os.close(handle)
            except OSError:
                pass

    def launch(self, first=0, second=0, mode="parallel", messages=("first diagnostic", "second diagnostic")):
        gates = [os.pipe(), os.pipe()]
        self.events, event_writer = os.pipe()
        self.handles.extend([self.events, gates[0][1], gates[1][1]])
        self.gates = dict(first=gates[0][1], second=gates[1][1])
        commands = []
        for name, gate, status, message in zip(("first", "second"), gates, (first, second), messages):
            args = [sys.executable, str(self.worker), name, str(self.root), str(gate[0]), str(event_writer), str(status), message]
            commands.append("exec " + " ".join(driver.q(arg) for arg in args))
        inherited = [event_writer, gates[0][0], gates[1][0]]
        try:
            self.process = subprocess.Popen([sys.executable, "-c", LAUNCH, str(ROOT), *commands, str(self.root), mode],
                                            cwd=ROOT, pass_fds=inherited, start_new_session=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        finally:
            for handle in inherited:
                os.close(handle)

    def event(self):
        deadline = time.monotonic() + 10
        while not self.pending:
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0, "worker rendezvous deadlocked")
            readable, _, _ = select.select([self.events], [], [], remaining)
            self.assertTrue(readable, "worker rendezvous deadlocked")
            chunk = os.read(self.events, 4096)
            self.assertTrue(chunk, "worker event pipe closed before rendezvous")
            self.buffer += chunk
            lines = self.buffer.split(b"\n")
            self.buffer = lines.pop()
            self.pending.extend(json.loads(line) for line in lines)
        return self.pending.pop(0)

    def release(self, name):
        os.write(self.gates[name], b"x")

    def ready(self):
        records = [self.event(), self.event()]
        self.assertEqual({record["name"] for record in records}, {"first", "second"})
        self.assertEqual({record["phase"] for record in records}, {"ready"})
        self.assertFalse(any(record["other_done"] for record in records))
        self.assertFalse(any(self.root.glob("*.done")))
        return records

    def finish(self, expected, messages=("first diagnostic", "second diagnostic")):
        stdout, stderr = self.process.communicate(timeout=10)
        self.assertEqual(self.process.returncode, expected, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "\n".join(messages) + "\n")
        self.assertEqual(json.loads((self.root / "joined.json").read_text()), [True, True])
        self.assertEqual({path.stem for path in self.root.glob("*.done")}, {"first", "second"})
        return stdout, stderr

    def test_both_jobs_reach_a_barrier_before_either_can_finish(self):
        self.launch()
        records = self.ready()
        self.assertEqual(len({record["pid"] for record in records}), 2)
        for name in ("first", "second"):
            self.release(name)
        self.finish(0)
        for record in records:
            with self.assertRaises(ProcessLookupError):
                os.kill(record["pid"], 0)

    def test_serial_negative_control_cannot_produce_the_overlap_witness(self):
        self.launch(mode="serial")
        first = self.event()
        self.assertEqual((first["phase"], first["name"], first["other_done"]), ("ready", "first", False))
        self.release("first")
        self.assertEqual(self.event()["phase"], "done")
        second = self.event()
        self.assertEqual((second["phase"], second["name"], second["other_done"]), ("ready", "second", True))
        self.release("second")
        self.finish(0)

    def test_diagnostics_follow_job_order_even_when_second_finishes_first(self):
        self.launch()
        self.ready()
        self.release("second")
        finished = self.event()
        self.assertEqual((finished["phase"], finished["name"]), ("done", "second"))
        self.release("first")
        self.finish(0)

    def test_first_failure_is_reported_after_both_jobs_finish(self):
        self.launch(first=7)
        self.ready()
        self.release("first")
        self.assertEqual(self.event()["name"], "first")
        self.release("second")
        self.finish(7)

    def test_second_failure_is_reported(self):
        self.launch(second=9)
        self.ready()
        self.release("first")
        self.release("second")
        self.finish(9)

    def test_simultaneous_failures_select_first_job(self):
        self.launch(first=7, second=9)
        self.ready()
        self.release("second")
        self.assertEqual(self.event()["name"], "second")
        self.release("first")
        self.finish(7)

    def test_primary_failure_suppresses_secondary_diagnostics_and_joins(self):
        messages = ("runtime.py:1: error: frontend rejected", "runtime.c:2: error: secondary failure")
        self.launch(first=7, second=9, mode="primary", messages=messages)
        records = self.ready()
        self.release("first")
        self.assertEqual(self.event()["name"], "first")
        self.release("second")
        self.finish(7, messages[:1])
        self.assertEqual(int((self.root / "worker-first.status").read_text()), 7)
        for record in records:
            with self.assertRaises(ProcessLookupError):
                os.kill(record["pid"], 0)

    def test_successful_primary_preserves_secondary_failure(self):
        self.launch(second=9, mode="primary")
        self.ready()
        self.release("second")
        self.assertEqual(self.event()["name"], "second")
        self.release("first")
        self.finish(9)
        self.assertEqual(int((self.root / "worker-first.status").read_text()), 0)

    def test_quoted_paths_and_diagnostics_are_literal(self):
        messages = ("first ' $(echo forbidden) `uname` ; & $HOME", 'second " quoted\\path\nnext line')
        self.launch(messages=messages)
        self.ready()
        self.release("first")
        self.release("second")
        self.finish(0, messages)

    def test_term_drains_both_jobs_before_returning(self):
        self.launch()
        records = self.ready()
        parents = {record["parent"] for record in records}
        self.assertEqual(len(parents), 1)
        os.kill(parents.pop(), signal.SIGTERM)
        self.release("first")
        self.release("second")
        self.finish(143)
        for record in records:
            with self.assertRaises(ProcessLookupError):
                os.kill(record["pid"], 0)


class RuntimeSnapshotProtocol(unittest.TestCase):
    def test_worker_reads_snapshot_with_original_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "snapshot.py"
            original = root / "original name.py"
            output = root / "output.ll"
            snapshot.write_text("snapshot bytes\n")
            original.write_text("newer live bytes\n")
            argv = [str(ROOT / "pystachy.py"), "rt-cache", str(snapshot), str(original), "-o", str(output)]
            with patch.object(sys, "argv", argv), patch.object(diagnostics, "SRC", "initial.py"):
                with patch.object(driver, "runtime_ir", return_value="; worker IR\n") as compile_runtime:
                    driver.main()
                    compile_runtime.assert_called_once_with(str(original), "snapshot bytes\n", True)
                    self.assertEqual(diagnostics.SRC, str(original))
            self.assertEqual(output.read_text(), "; worker IR\n")

    def test_worker_requires_the_complete_internal_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.py"
            snapshot.write_text("snapshot bytes\n")
            for arguments in ((), ("source.py",), ("source.py", "-x", "out.ll")):
                argv = ["pystachy", "rt-cache", str(snapshot), *arguments]
                with self.subTest(arguments=arguments), patch.object(sys, "argv", argv):
                    with patch.object(diagnostics, "SRC", "initial.py"), contextlib.redirect_stderr(io.StringIO()) as output:
                        with self.assertRaises(SystemExit) as caught:
                            driver.main()
                        self.assertEqual(caught.exception.code, 1)
                        self.assertIn("invalid runtime cache worker arguments", output.getvalue())


if __name__ == "__main__":
    unittest.main()
