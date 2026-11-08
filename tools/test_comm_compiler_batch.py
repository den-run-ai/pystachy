"""Real process failure/ordering controls for the compiler dogfood coordinator."""

import ctypes
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comm_compiler_batch", ROOT / "examples" / "comm" / "compiler_batch.py")
assert SPEC is not None and SPEC.loader is not None
BATCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BATCH
SPEC.loader.exec_module(BATCH)


@unittest.skipUnless(os.name == "posix", "pipe readiness and process-group backend is POSIX-only")
class CompilerBatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def job(self, index, source, expected_status=0):
        return BATCH.Job(index, [sys.executable, "-c", source], self.directory / f"{index}.ll",
                         expected_status=expected_status)

    def test_later_job_completes_while_earlier_job_is_blocked(self):
        # Job 1 releases job 0 only after its own stderr was drained.  Both
        # produce >pipe-capacity diagnostics, so input-order communicate deadlocks.
        marker = self.directory / "released"
        first = "import os,time,sys\nsys.stderr.write('a' * 131072); sys.stderr.flush()\n"
        first += f"while not os.path.exists({str(marker)!r}): time.sleep(0.005)\n"
        first += "time.sleep(0.15)\nprint('first')\n"
        second = "import sys\nfrom pathlib import Path\nsys.stderr.write('b' * 131072); sys.stderr.flush()\n"
        second += f"Path({str(marker)!r}).write_text('released')\nprint('second')\n"
        result = BATCH.run_batch([self.job(0, first), self.job(1, second)], timeout=3)
        self.assertEqual(result["completion_order"], [1, 0])
        self.assertEqual(result["peak_admitted"], 2)
        self.assertEqual({record["diagnostics"]["stderr"]["bytes"] for record in result["records"]}, {131072})
        self.assertTrue(result["diagnostic_order"])
        self.assertEqual((self.directory / "0.ll").read_bytes(), b"first\n")

    def test_serial_admission_is_bounded(self):
        result = BATCH.run_batch([self.job(i, f"print({i})") for i in range(4)], workers=1)
        self.assertEqual(result["peak_admitted"], 1)
        self.assertEqual(result["completion_order"], [0, 1, 2, 3])

    def test_diagnostics_limit_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "diagnostics exceed"):
            BATCH.run_batch([self.job(0, "import sys; sys.stderr.write('x' * 65536); print('ok')")], diagnostic_limit=100)

    def test_exit_status_is_validated_and_expected_failure_is_recorded(self):
        with self.assertRaisesRegex(RuntimeError, "exited 7"):
            BATCH.run_batch([self.job(0, "raise SystemExit(7)")])
        result = BATCH.run_batch([self.job(1, "raise SystemExit(7)", expected_status=7)])
        self.assertEqual(result["records"][0]["status"], 7)
        self.assertIsNone(result["records"][0]["sha256"])

    def test_timeout_kills_and_reaps_process(self):
        pid_path = self.directory / "pid"
        source = f"import os,time; open({str(pid_path)!r},'w').write(str(os.getpid())); time.sleep(60)"
        with self.assertRaises(TimeoutError):
            BATCH.run_batch([self.job(0, source)], timeout=0.3)
        self.assertTrue(pid_path.is_file())
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid_path.read_text()), 0)

    def test_descendant_held_pipe_obeys_deadline(self):
        source = "import subprocess,sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); print('done')"
        with self.assertRaises(TimeoutError):
            BATCH.run_batch([self.job(0, source)], timeout=0.3)

    def test_stale_artifacts_and_duplicate_ids_rejected(self):
        (self.directory / "0.ll").write_text("stale")
        with self.assertRaises(FileExistsError):
            BATCH.run_batch([self.job(0, "print('new')")])
        self.assertEqual((self.directory / "0.ll").read_text(), "stale")
        with self.assertRaisesRegex(ValueError, "IDs"):
            BATCH.run_batch([self.job(1, "print(1)"), self.job(1, "print(2)")])

    def test_persistent_handler_receives_real_completion_records(self):
        handler = [sys.executable, "-u", "-c",
                   "import sys\nfor line in sys.stdin.buffer:\n sys.stdout.buffer.write(line); sys.stdout.buffer.flush()"]
        result = BATCH.run_batch([self.job(i, f"print({i})") for i in range(5)], workers=2,
                                 transport="handler", handler_command=handler)
        self.assertEqual(len(result["records"]), 5)
        self.assertLessEqual(result["peak_admitted"], 2)

    def test_handler_corruption_is_rejected(self):
        handler = [sys.executable, "-u", "-c", "import sys\nfor line in sys.stdin.buffer: print('wrong')"]
        with self.assertRaisesRegex(AssertionError, "changed or truncated"):
            BATCH.run_batch([self.job(0, "print('ok')")], transport="handler", handler_command=handler)

    def test_handler_stall_is_bounded(self):
        handler = [sys.executable, "-c", "import time; time.sleep(60)"]
        with self.assertRaises(TimeoutError):
            BATCH.run_batch([self.job(0, "print('ok')")], transport="handler", handler_command=handler, timeout=0.3)

    def test_handler_extra_output_and_stderr_are_rejected(self):
        for index, trailing in enumerate(["print('extra')", "sys.stderr.write('bad')"]):
            source = "import sys\nfor line in sys.stdin.buffer:\n sys.stdout.buffer.write(line); sys.stdout.buffer.flush()\n" + trailing
            with self.subTest(trailing=trailing):
                with self.assertRaisesRegex(RuntimeError, "unexpected output"):
                    BATCH.run_batch([self.job(index, "print('ok')")], transport="handler",
                                    handler_command=[sys.executable, "-u", "-c", source])

    def test_previous_signal_handlers_are_restored(self):
        previous = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
        custom_calls = []
        original_popen = subprocess.Popen
        original_kill_group = BATCH.kill_group

        def custom_handler(signum, frame):
            custom_calls.append(signum)

        try:
            for signum in previous:
                signal.signal(signum, custom_handler)
            for index, outcome in enumerate(("success", "failure", "signal", "late_signal")):
                with self.subTest(outcome=outcome):
                    if outcome == "success":
                        BATCH.run_batch([self.job(index, "print('ok')")])
                    elif outcome == "failure":
                        with self.assertRaises(RuntimeError):
                            BATCH.run_batch([self.job(index, "raise SystemExit(7)")])
                    elif outcome == "signal":
                        def interrupted_spawn(*args, **kwargs):
                            process = original_popen(*args, **kwargs)
                            os.kill(os.getpid(), signal.SIGTERM)
                            return process

                        with patch.object(BATCH.subprocess, "Popen", interrupted_spawn):
                            with self.assertRaises(SystemExit) as raised:
                                BATCH.run_batch([self.job(index, "print('ok')")])
                        self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
                    else:
                        def interrupted_cleanup(process):
                            os.kill(os.getpid(), signal.SIGTERM)
                            original_kill_group(process)

                        with patch.object(BATCH, "kill_group", interrupted_cleanup):
                            with self.assertRaises(SystemExit) as raised:
                                BATCH.run_batch([self.job(index, "print('ok')")])
                        self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
                    for signum in previous:
                        self.assertIs(signal.getsignal(signum), custom_handler)
            self.assertEqual(custom_calls, [])
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)

    def test_non_main_thread_rejected_before_launch(self):
        errors = []

        def run_in_thread():
            try:
                BATCH.run_batch([self.job(0, "print('ok')")])
            except BaseException as error:
                errors.append(error)

        with patch.object(BATCH.subprocess, "Popen", side_effect=AssertionError("unexpected launch")) as launch:
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            launch.assert_not_called()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertIn("main thread", str(errors[0]))
        self.assertFalse((self.directory / "0.ll").exists())

    def test_invalid_bounds_fail_before_launch(self):
        for bounds in [{"workers": 0}, {"workers": 9}, {"timeout": 0}, {"diagnostic_limit": 0}]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                BATCH.run_batch([], **bounds)


@unittest.skipUnless(os.name == "posix", "coordinator signal ownership is POSIX-only")
class CoordinatorSignalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.owned_pids = []
        self.coordinator = None
        if sys.platform.startswith("linux"):
            # Adopt orphaned test grandchildren so even the unfixed negative
            # control can be cleaned up without depending on container PID 1.
            libc = ctypes.CDLL(None, use_errno=True)
            previous = ctypes.c_int()
            self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
            self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
            self.addCleanup(libc.prctl, 36, previous.value, 0, 0, 0)
        self.addCleanup(self.cleanup_processes)

    def cleanup_processes(self):
        if self.coordinator is not None and self.coordinator.poll() is None:
            self.coordinator.kill()
        for pid in self.owned_pids:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.coordinator is not None:
            self.coordinator.communicate(timeout=5)
        for pid in self.owned_pids:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass

    def wait_for(self, predicate, message):
        deadline = time.monotonic() + 5
        while not predicate():
            if time.monotonic() > deadline:
                self.fail(message)
            time.sleep(0.01)

    def assert_gone(self, pid, *, descendant=False):
        def gone():
            if descendant:
                try:
                    if os.waitpid(pid, os.WNOHANG)[0] == pid:
                        return True
                except ChildProcessError:
                    pass
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            return False
        self.wait_for(gone, f"owned process {pid} survived coordinator cancellation")

    def exercise_signal(self, signum, *, handler=False, descendants=False, during_spawn=False,
                        during_cleanup=False, handler_shutdown=False):
        worker_pid = self.directory / "worker.pid"
        descendant_pid = self.directory / "descendant.pid"
        handler_pid = self.directory / "handler.pid"
        shutdown_marker = self.directory / "handler.shutdown"
        launched_pids = self.directory / "launched.pids"
        worker_source = "import os,signal,subprocess,sys,time\nfrom pathlib import Path\n"
        # These children must be killed even if they ignore graceful termination.
        worker_source += "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        if descendants:
            child_source = ("import os,signal,time; from pathlib import Path; "
                            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                            f"Path({str(descendant_pid)!r}).write_text(str(os.getpid())); time.sleep(60)")
            worker_source += f"subprocess.Popen([sys.executable, '-c', {child_source!r}])\n"
        if not during_spawn:
            worker_source += f"Path({str(worker_pid)!r}).write_text(str(os.getpid()))\n"
        worker_source += "print(1)\n" if handler_shutdown else "time.sleep(60)\n"
        handler_source = ("import os,signal,sys,time\nfrom pathlib import Path\n"
                          "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                          f"Path({str(handler_pid)!r}).write_text(str(os.getpid()))\n")
        if handler_shutdown:
            handler_source += (
                "for line in sys.stdin.buffer:\n"
                "    sys.stdout.buffer.write(line)\n"
                "    sys.stdout.buffer.flush()\n"
                f"Path({str(shutdown_marker)!r}).write_text('ready')\n"
            )
        handler_source += "time.sleep(60)\n"
        coordinator_source = (
            "import os,signal,subprocess,sys\nfrom pathlib import Path\n"
            f"sys.path.insert(0, {str(ROOT / 'examples' / 'comm')!r})\n"
            "import compiler_batch as batch\n"
        )
        # Record every owned group before readiness, allowing fixture cleanup
        # even when a worker fails before writing its own PID file.
        coordinator_source += (
            "original_popen = subprocess.Popen\n"
            "def tracked_spawn(*args, **kwargs):\n"
            "    process = original_popen(*args, **kwargs)\n"
            f"    with open({str(launched_pids)!r}, 'a') as stream:\n"
            "        stream.write(str(process.pid) + '\\n')\n"
        )
        if during_spawn:
            # Trigger the ownership gap after a successful Popen but before the
            # caller can append it to its cleanup list. No scheduler sleep race.
            reported_pid = handler_pid if handler else worker_pid
            coordinator_source += (
                f"    Path({str(reported_pid)!r}).write_text(str(process.pid))\n"
                f"    os.kill(os.getpid(), {int(signum)})\n"
            )
        coordinator_source += "    return process\nsubprocess.Popen = tracked_spawn\n"
        if during_cleanup:
            coordinator_source += (
                "original_kill_group = batch.kill_group\n"
                "def interrupted_cleanup(process):\n"
                "    os.kill(os.getpid(), signal.SIGINT)\n"
                "    os.kill(os.getpid(), signal.SIGTERM)\n"
                "    original_kill_group(process)\n"
                "batch.kill_group = interrupted_cleanup\n"
            )
        coordinator_source += (
            f"job = batch.Job(0, [sys.executable, '-c', {worker_source!r}], "
            f"Path({str(self.directory / 'artifact.ll')!r}))\n"
            f"batch.run_batch([job], timeout=30, transport={'handler' if handler else 'direct'!r}, "
            f"handler_command=[sys.executable, '-c', {handler_source!r}])\n"
        )
        self.coordinator = subprocess.Popen([sys.executable, "-c", coordinator_source],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            start_new_session=True)
        paths = [] if handler and during_spawn else [worker_pid]
        if handler:
            paths.append(handler_pid)
        if descendants:
            paths.append(descendant_pid)
        try:
            self.wait_for(lambda: all(path.is_file() and path.read_text() for path in paths),
                          "worker/handler did not report its PID")
            if handler_shutdown:
                self.wait_for(shutdown_marker.is_file, "handler did not reach shutdown")
        finally:
            # Collect partial readiness too, so a fixture startup failure is safe.
            owned = {int(path.read_text()) for path in paths if path.is_file() and path.read_text()}
            if launched_pids.is_file():
                owned.update(int(pid) for pid in launched_pids.read_text().splitlines())
            self.owned_pids.extend(owned)
        if not during_spawn:
            self.coordinator.send_signal(signum)
        stdout, stderr = self.coordinator.communicate(timeout=3 if handler_shutdown else 5)
        self.assertIn(self.coordinator.returncode, (-signum, 128 + signum),
                      (stdout, stderr))
        for path in paths:
            self.assert_gone(int(path.read_text()), descendant=path == descendant_pid)

    def test_sigterm_reaps_worker(self):
        self.exercise_signal(signal.SIGTERM)

    def test_sigint_reaps_worker(self):
        self.exercise_signal(signal.SIGINT)

    def test_sigterm_reaps_persistent_handler(self):
        self.exercise_signal(signal.SIGTERM, handler=True)

    def test_sigint_reaps_persistent_handler(self):
        self.exercise_signal(signal.SIGINT, handler=True)

    @unittest.skipUnless(sys.platform.startswith("linux"), "subreaper avoids orphan test descendants")
    def test_sigterm_kills_worker_descendants(self):
        self.exercise_signal(signal.SIGTERM, descendants=True)

    def test_sigterm_after_spawn_before_registration(self):
        self.exercise_signal(signal.SIGTERM, during_spawn=True)

    def test_sigint_after_spawn_before_registration(self):
        self.exercise_signal(signal.SIGINT, during_spawn=True)

    def test_repeated_signals_do_not_interrupt_cleanup(self):
        self.exercise_signal(signal.SIGTERM, handler=True, during_cleanup=True)

    def test_sigterm_after_handler_spawn_before_registration(self):
        self.exercise_signal(signal.SIGTERM, handler=True, during_spawn=True)

    def test_sigterm_during_handler_shutdown(self):
        self.exercise_signal(signal.SIGTERM, handler=True, handler_shutdown=True)


if __name__ == "__main__":
    unittest.main()
