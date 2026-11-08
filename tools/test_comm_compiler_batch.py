"""Real process failure/ordering controls for the compiler dogfood coordinator."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest


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

    def test_invalid_bounds_fail_before_launch(self):
        for bounds in [{"workers": 0}, {"workers": 9}, {"timeout": 0}, {"diagnostic_limit": 0}]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                BATCH.run_batch([], **bounds)


if __name__ == "__main__":
    unittest.main()
