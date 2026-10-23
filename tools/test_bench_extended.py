"""Failure-path checks for the benchmark controller; LLVM is not required."""
import contextlib
import io
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

import bench_extended as bench


class OutputTests(unittest.TestCase):
    def test_valid_samples_keep_first_call_separate(self):
        result = bench.parse_output(
            "first 42 9000000000\nwarmup 42\nsample 42 2000000000\nsample 42 4000000000\n",
            warmups=1, samples=2, expected=42,
        )
        self.assertEqual(result["checksum"], 42)
        self.assertEqual(result["first_s"], 9.0)
        self.assertEqual(result["samples_s"], [2.0, 4.0])

    def test_every_call_must_match_the_oracle(self):
        for row in range(3):
            lines = ["first 42 100", "warmup 42", "sample 42 200"]
            lines[row] = lines[row].replace("42", "43")
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, "checksum"):
                bench.parse_output("\n".join(lines), 1, 1, expected=42)

    def test_oracle_must_itself_be_repeatable(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            bench.parse_output("first 42 100\nsample 43 200\n", 0, 1)

    def test_missing_extra_and_malformed_rows_are_rejected(self):
        outputs = [
            "",  # No successful work is not a benchmark result.
            "first 42 100\n",  # Missing sample.
            "first 42 100\nsample 42 200\nsample 42 300\n",
            "first 42 100\nsample 42 200\nnoise\n",
            "sample 42 100\nfirst 42 200\n",  # Wrong phase order.
            "first 42 100\nsample 42\n",
            "first 42 100\nsample 42 200 extra\n",
            "first NaN 100\nsample 42 200\n",
            "first 42 100\nsample 42 NaN\n",
            "first 42 100\nsample 42 -1\n",
            "first 42 100\nsample 42 0\n",
        ]
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(ValueError):
                bench.parse_output(output, 0, 1, expected=42)


class ProcessTests(unittest.TestCase):
    def test_successful_command_keeps_output_and_diagnostics_separate(self):
        result = bench.execute(
            [sys.executable, "-c", "import sys; print('checksum'); print('diagnostic', file=sys.stderr)"],
            dict(os.environ), 5,
        )
        self.assertEqual(result["stdout"], "checksum\n")
        self.assertEqual(result["stderr"], "diagnostic\n")
        self.assertEqual(result["returncode"], 0)
        self.assertGreaterEqual(result["wall_s"], 0)

    def test_nonzero_exit_fails_even_with_valid_benchmark_output(self):
        code = "import sys; print('first 42 100'); print('sample 42 200'); print('broken', file=sys.stderr); sys.exit(7)"
        with self.assertRaisesRegex(RuntimeError, "exit 7") as caught:
            bench.execute([sys.executable, "-c", code], dict(os.environ), 5)
        self.assertIn("broken", str(caught.exception))

    @unittest.skipUnless(os.name == "posix" and Path("/proc/self/stat").exists(),
                         "process-group liveness check requires Linux /proc")
    def test_timeout_kills_grandchild_holding_output_pipe(self):
        # Killing only the direct child leaves the grandchild holding stdout/stderr
        # open: communicate() would wait ten seconds, and the marker would appear.
        # The child is finite even under that regression; cleanup is also explicit.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            pidfile = directory / "grandchild.pid"
            groupfile = directory / "group.pid"
            marker = directory / "survived"
            grandchild = (
                "import os, pathlib, time; "
                f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid())); "
                "time.sleep(10); "
                f"pathlib.Path({str(marker)!r}).write_text('still running')"
            )
            parent = (
                "import os, pathlib, subprocess, sys; "
                f"pathlib.Path({str(groupfile)!r}).write_text(str(os.getpid())); "
                f"subprocess.run([sys.executable, '-c', {grandchild!r}], check=True)"
            )
            started = time.monotonic()
            try:
                with self.assertRaisesRegex(RuntimeError, "timeout"):
                    bench.execute([sys.executable, "-c", parent], dict(os.environ), 2)
                self.assertLess(time.monotonic() - started, 7,
                                "a descendant kept the output pipe open after timeout")
                self.assertTrue(pidfile.exists(), "grandchild never started; timeout test is inconclusive")
                self.assertFalse(marker.exists(), "grandchild survived its process group's timeout")
                stat = Path("/proc") / pidfile.read_text() / "stat"
                # SIGKILL closes the grandchild's files, which ends the pipe, before it becomes a
                # zombie: it reads as running (or in disk sleep) while it exits, longer on a busy host
                deadline = time.monotonic() + 5
                while True:
                    try:
                        state = stat.read_text().rsplit(")", 1)[1].split()[0]
                    except (FileNotFoundError, ProcessLookupError):
                        # The process can disappear after /proc opens the file, before read().
                        state = None
                    if state not in ("R", "D") or time.monotonic() > deadline:
                        break
                    time.sleep(0.01)
                # An orphan may remain a zombie until the container's init reaps it.
                self.assertIn(state, (None, "Z", "X"), "grandchild is still executing")
            finally:
                if groupfile.exists():
                    try:
                        os.killpg(int(groupfile.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass


class ArgumentTests(unittest.TestCase):
    def test_invalid_work_or_timeout_settings_fail_before_execution(self):
        for arguments in (["--processes", "0"], ["--samples", "0"], ["--warmups", "-1"],
                          ["--scale", "nan"], ["--scale", "0"], ["--scale", "1e308"], ["--timeout", "inf"],
                          ["--timeout", "-1"], ["--compiler", ""]):
            with self.subTest(arguments=arguments), mock.patch.object(bench, "execute") as execute:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    bench.main(arguments)
                self.assertEqual(caught.exception.code, 2)
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
