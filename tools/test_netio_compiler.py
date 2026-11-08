"""Compiler I/O dogfood must preserve failures and bound every owned child."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples/netio"
SPEC = importlib.util.spec_from_file_location("compiler_netio_check", HERE / "check.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
SPEC = importlib.util.spec_from_file_location("netio_compiler_dogfood", HERE / "compiler_dogfood.py")
dogfood = importlib.util.module_from_spec(SPEC)
with mock.patch.dict(sys.modules, {"check": check}):
    SPEC.loader.exec_module(dogfood)


class CompilerPipeTests(unittest.TestCase):
    def test_completion_parser_preserves_binary_empty_streams_and_order(self):
        data, order = dogfood.parse_output(b"done 2 ff000a\ndone 0 4952\ndone 1 \n", 3, 3)
        self.assertEqual(data, [b"IR", b"", b"\xff\x00\n"])
        self.assertEqual(order, [2, 0, 1])

    def test_completion_parser_rejects_missing_duplicate_or_corrupt_records(self):
        cases = [(b"done 0 41", 1, 1), (b"done 0 41\n", 2, 1),
                 (b"done 0 \ndone 0 \n", 2, 1), (b"done 1 \n", 1, 1),
                 (b"done -1 \n", 1, 1), (b"done 00 \n", 1, 1), (b"done 0 FF\n", 1, 1),
                 (b"done 0 4 1\n", 1, 1), (b"done 0 zz\n", 1, 1), (b"done 0 \xff\n", 1, 1),
                 (b"done 0 4142\n", 1, 1), (b"extra\ndone 0 \n", 1, 1)]
        for output, streams, maximum in cases:
            with self.subTest(output=output), self.assertRaises(ValueError):
                dogfood.parse_output(output, streams, maximum)

    def test_reference_retains_nonzero_status_and_binary_diagnostics(self):
        command = [sys.executable, "-c", "import os; os.write(1,b'IR\\x00'); os.write(2,b'bad\\xff'); exit(7)"]
        result, wall = dogfood.serial(command, os.environ.copy(), ROOT, 5, 1024)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (7, b"IR\x00", b"bad\xff"))
        self.assertGreater(wall, 0)

    def test_reference_enforces_output_bound(self):
        command = [sys.executable, "-c", "import os; os.write(1,b'x'*1000000)"]
        with self.assertRaisesRegex(ValueError, "exceeds configured bound"):
            dogfood.serial(command, os.environ.copy(), ROOT, 5, 16)

    def test_real_oracle_collects_both_streams_and_preserves_failed_job(self):
        commands = [[sys.executable, "-c", "import os; os.write(1,b'IR\\x00\\xff\\n')"],
                    [sys.executable, "-c", "import os; os.write(2,b'diagnostic\\n'); exit(1)"]]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "drain.py"
            source.write_bytes((HERE / "drain.py").read_bytes())
            env = check.environment(directory, oracle=True)
            actual, timings = dogfood.collect(commands, [sys.executable, str(source)], env, env, directory, 5, 128)
            descriptors = [row["passed_fd"] for row in timings["descriptor_mapping"]]
            self.assertEqual(len(descriptors), 4)
            self.assertEqual(len(set(descriptors)), 4)
            self.assertTrue(all(fd >= dogfood.FIRST_INHERITED_FD for fd in descriptors))
            for fd in descriptors:
                with self.assertRaises(OSError):
                    os.fstat(fd)
            for command, result in zip(commands, actual):
                reference, wall = dogfood.serial(command, env, directory, 5, 128)
                dogfood.compare("oracle", result, reference)
            self.assertEqual(sorted(timings["completion_order"]), [0, 1, 2, 3])
            self.assertGreater(timings["end_to_end_s"], 0)
            self.assertEqual(actual[1].returncode, 1)

    def test_duplicate_is_non_inheritable_and_closed_after_failed_scope(self):
        read_fd, write_fd = os.pipe()
        try:
            with self.assertRaisesRegex(RuntimeError, "stop"), dogfood.Owned() as owned:
                duplicate = owned.duplicate(read_fd)
                self.assertFalse(os.get_inheritable(duplicate))
                self.assertGreaterEqual(duplicate, 64)
                os.write(write_fd, b"probe")
                self.assertEqual(os.read(duplicate, 5), b"probe")
                raise RuntimeError("stop")
            with self.assertRaises(OSError):
                os.fstat(duplicate)
            os.fstat(read_fd)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_signal_between_duplicate_and_ownership_record_cleans_descriptor(self):
        original = dogfood.fcntl.fcntl
        duplicates = []

        def interrupted(*args):
            duplicate = original(*args)
            duplicates.append(duplicate)
            os.kill(os.getpid(), signal.SIGTERM)
            return duplicate

        read_fd, write_fd = os.pipe()
        try:
            with mock.patch.object(dogfood.fcntl, "fcntl", side_effect=interrupted), \
                    self.assertRaisesRegex(dogfood.Cancelled, "cancelled"), dogfood.Owned() as owned:
                owned.duplicate(read_fd)
            self.assertEqual(len(duplicates), 1)
            with self.assertRaises(OSError):
                os.fstat(duplicates[0])
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_bridge_build_uses_supplied_owned_runner(self):
        processes, start = self.track_processes()
        command = [sys.executable, "-c", "import os,signal,sys,time; os.kill(int(sys.argv[1]),signal.SIGTERM); time.sleep(30)",
                   str(os.getpid())]
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(dogfood.subprocess, "Popen", side_effect=start), \
                self.assertRaisesRegex(dogfood.Cancelled, "cancelled"):
            check.build_bridge(Path(temporary), os.environ.copy(), command, 5, runner=dogfood.run)
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].returncode)

    def test_consumed_source_inventory_includes_runtime_support(self):
        recorded = dogfood.sources()
        for path in ("runtime.c", "runtime.py", "mpz/mpz.c", "ryu/d2s.c", "ryu/ryu.h",
                     "examples/netio/drain.py", "tools/rt_cpython/ffi.py"):
            self.assertIn(path, recorded)

    def test_status_and_diagnostics_are_part_of_exact_comparison(self):
        reference = subprocess.CompletedProcess(["compiler"], 1, b"", b"syntax\x00\xff")
        dogfood.compare("same", reference, reference)
        for result in (subprocess.CompletedProcess([], 0, reference.stdout, reference.stderr),
                       subprocess.CompletedProcess([], 1, b"extra", reference.stderr),
                       subprocess.CompletedProcess([], 1, reference.stdout, b"syntax")):
            with self.subTest(result=result), self.assertRaisesRegex(ValueError, "differs from serial"):
                dogfood.compare("broken", result, reference)

    def track_processes(self):
        processes = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process

        return processes, start

    def test_collector_failure_reaps_all_workers(self):
        processes, start = self.track_processes()
        commands = [[sys.executable, "-c", "import time; time.sleep(30)"]] * 2
        with mock.patch.object(dogfood.subprocess, "Popen", side_effect=start), self.assertRaisesRegex(RuntimeError, "exit=3"):
            dogfood.collect(commands, [sys.executable, "-c", "exit(3)"], os.environ.copy(), os.environ.copy(), ROOT, 5, 128)
        self.assertEqual(len(processes), 3)
        self.assertTrue(all(process.returncode is not None for process in processes))
        self.assertTrue(all(process.stdout.closed and process.stderr.closed for process in processes))

    def test_deadline_reaps_workers_and_collector(self):
        processes, start = self.track_processes()
        command = [sys.executable, "-c", "import time; time.sleep(30)"]
        with mock.patch.object(dogfood.subprocess, "Popen", side_effect=start), self.assertRaisesRegex(TimeoutError, "deadline"):
            dogfood.collect([command], command, os.environ.copy(), os.environ.copy(), ROOT, 0.2, 128)
        self.assertEqual(len(processes), 2)
        self.assertTrue(all(process.returncode is not None for process in processes))

    def test_partial_launch_failure_reaps_existing_worker(self):
        processes, start = self.track_processes()

        def failing(*args, **kwargs):
            if processes:
                raise OSError("second worker launch failed")
            return start(*args, **kwargs)

        command = [sys.executable, "-c", "import time; time.sleep(30)"]
        with mock.patch.object(dogfood.subprocess, "Popen", side_effect=failing), self.assertRaisesRegex(OSError, "second worker"):
            dogfood.collect([command, command], command, os.environ.copy(), os.environ.copy(), ROOT, 5, 128)
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].returncode)

    def test_signals_during_launch_and_cleanup_do_not_lose_child(self):
        for signum in (signal.SIGTERM, signal.SIGINT):
            handlers = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
            processes, start = self.track_processes()
            original_cleanup = dogfood.cleanup

            def interrupted(*args, start=start, signum=signum, **kwargs):
                process = start(*args, **kwargs)
                os.kill(os.getpid(), signum)
                return process

            def repeated(items, original_cleanup=original_cleanup):
                os.kill(os.getpid(), signal.SIGTERM)
                os.kill(os.getpid(), signal.SIGINT)
                original_cleanup(items)

            with self.subTest(signum=signum), mock.patch.object(dogfood.subprocess, "Popen", side_effect=interrupted), \
                    mock.patch.object(dogfood, "cleanup", side_effect=repeated), self.assertRaisesRegex(dogfood.Cancelled, "cancelled"):
                dogfood.serial([sys.executable, "-c", "import time; time.sleep(30)"], os.environ.copy(), ROOT, 5, 128)
            self.assertEqual(len(processes), 1)
            self.assertIsNotNone(processes[0].returncode)
            self.assertEqual({number: signal.getsignal(number) for number in handlers}, handlers)

    def test_sigterm_during_collection_cleans_compiler_group(self):
        processes, start = self.track_processes()
        worker = [sys.executable, "-c", "import time; time.sleep(30)"]
        consumer = [sys.executable, "-c", "import os,signal,sys,time; os.kill(int(sys.argv[1]), signal.SIGTERM); time.sleep(1)",
                    str(os.getpid())]
        handlers = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}
        with mock.patch.object(dogfood.subprocess, "Popen", side_effect=start), self.assertRaisesRegex(dogfood.Cancelled, "cancelled"):
            dogfood.collect([worker], consumer, os.environ.copy(), os.environ.copy(), ROOT, 5, 128)
        self.assertEqual(len(processes), 2)
        self.assertTrue(all(process.returncode is not None for process in processes))
        self.assertEqual({number: signal.getsignal(number) for number in handlers}, handlers)

    def test_signal_arriving_during_successful_cleanup_is_not_lost(self):
        original_cleanup = dogfood.cleanup

        def interrupted(items):
            os.kill(os.getpid(), signal.SIGTERM)
            original_cleanup(items)

        with mock.patch.object(dogfood, "cleanup", side_effect=interrupted), self.assertRaisesRegex(dogfood.Cancelled, "cancelled"):
            dogfood.serial([sys.executable, "-c", "pass"], os.environ.copy(), ROOT, 5, 128)

    def test_failed_run_replaces_previous_success_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(json.dumps({"result": "pass", "runs": {"old": [1]}}))

            def fail(args, report):
                self.assertEqual(json.loads(path.read_text())["result"], "running")
                raise RuntimeError("IR mismatch")

            with mock.patch.object(dogfood, "verify", side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(dogfood.main(["--json", str(path)]), 1)
            report = json.loads(path.read_text())
            self.assertEqual(report["result"], "fail")
            self.assertIn("IR mismatch", report["error"])
            self.assertNotIn("runs", report)


if __name__ == "__main__":
    unittest.main()
