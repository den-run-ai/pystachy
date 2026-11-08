"""Boundary and failure controls for the persistent completion-record consumer."""

import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples" / "comm"
SPEC = importlib.util.spec_from_file_location("comm_benchmark", HERE / "benchmark.py")
assert SPEC is not None and SPEC.loader is not None
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class BenchmarkValidationTests(unittest.TestCase):
    def sample(self, stdout, *, returncode=0, stderr=""):
        result = subprocess.CompletedProcess(["workload"], returncode, stdout, stderr)
        with patch.object(BENCHMARK.subprocess, "run", return_value=result):
            with patch.object(BENCHMARK.time, "perf_counter", side_effect=[10.0, 11.0]):
                return BENCHMARK.checked_sample(["workload"], ("records", 2, 256), {})

    def test_valid_checksum_and_timing(self):
        result = self.sample("records 2 256 512.0 0.25\n")
        self.assertEqual(result["checksum"], 512)
        self.assertEqual(result["seconds"], 0.25)
        self.assertEqual(result["process_seconds"], 1.0)

    def test_nonfinite_or_wrong_checksum_fails(self):
        for value in ["nan", "inf", "-inf", "511", "513"]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "checksum"):
                self.sample(f"records 2 256 {value} 0.25\n")

    def test_invalid_timing_fails(self):
        for value in ["nan", "inf", "-inf", "0", "-0.1", "1.01"]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "timing"):
                self.sample(f"records 2 256 512 {value}\n")

    def test_wrong_shape_or_count_fails(self):
        for output in ["records 1 256 512 0.25", "records 2 255 512 0.25",
                       "reduce 2 256 512 0.25", "records 2 256 512 0.25 extra", ""]:
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "unexpected"):
                self.sample(output)

    def test_failure_or_diagnostics_cannot_be_timed(self):
        for status, stderr in [(1, ""), (0, "warning")]:
            with self.subTest(status=status, stderr=stderr), self.assertRaises(RuntimeError):
                self.sample("records 2 256 512 0.25", returncode=status, stderr=stderr)


class RecordWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shlex.split(os.environ.get("CC", "cc"))
        if not cc or shutil.which(cc[0]) is None:
            raise unittest.SkipTest("C compiler required for record consumer checks")
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        library = Path(cls.directory.name) / "libpystachy_comm.so"
        subprocess.run([*cc, "-std=c11", "-O2", "-fPIC", "-shared",
                        str(HERE / "bridge.c"), "-o", str(library)],
                       check=True, capture_output=True, timeout=30)
        cls.env = os.environ.copy()
        cls.env["LD_LIBRARY_PATH"] = cls.directory.name + os.pathsep + cls.env.get("LD_LIBRARY_PATH", "")
        cls.env["PYTHONPATH"] = os.pathsep.join([str(HERE), str(ROOT / "tools" / "rt_cpython")])

    def run_worker(self, data, optimized=False):
        flags = ["-O"] if optimized else []
        return subprocess.run([sys.executable, *flags, str(HERE / "record_worker.py")],
                              input=data, capture_output=True, env=self.env, timeout=5)

    def test_multiple_records_preserve_exact_bytes(self):
        data = b'{"id":7,"path":"a\\u0000b"}\n{"id":1,"status":2}\n'
        result = self.run_worker(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, data)

    def test_optimized_python_still_executes_progress(self):
        result = self.run_worker(b'{"id":1}\n', optimized=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'{"id":1}\n')

    def test_exact_record_limit(self):
        data = b"x" * 4095 + b"\n"
        result = self.run_worker(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, data)

    def test_empty_stream_has_no_synthetic_completion(self):
        result = self.run_worker(b"")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")

    def test_oversized_or_unterminated_record_is_not_acknowledged(self):
        for data in [b"x" * 4096 + b"\n", b"x" * 10000 + b"\n", b'{"id":1}']:
            with self.subTest(size=len(data)):
                result = self.run_worker(data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")

    def test_failure_does_not_acknowledge_later_records(self):
        result = self.run_worker(b'{"id":0}\n' + b"x" * 4096 + b"\n" + b'{"id":2}\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'{"id":0}\n')

    def test_non_ascii_protocol_is_rejected(self):
        result = self.run_worker('{"path":"雪"}\n'.encode())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
