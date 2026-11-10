"""The socket benchmark must reject bad bytes and incomplete measurements."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import selectors
import socket
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples/netio"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load("netio_benchmark_check", HERE / "check.py")
oracle = load("netio_benchmark_oracle", HERE / "oracle/netio.py")
with mock.patch.dict(sys.modules, {"check": check, "netio": oracle}):
    benchmark = load("netio_benchmark", HERE / "benchmark.py")
    workload = load("netio_benchmark_workload", HERE / "bench_workload.py")


class BenchmarkTests(unittest.TestCase):
    def test_all_cases_validate_real_binary_transfers(self):
        for case in benchmark.CASES:
            with self.subTest(case=case), contextlib.redirect_stdout(io.StringIO()) as output:
                workload.run(case, 2, 1, 2)
            result = benchmark.validate_measurement(output.getvalue().encode(), case, 2, 1, 2)
            self.assertEqual(result["checksum"], benchmark.BYTES_PER_ITERATION[case] * 2)
            self.assertEqual(len(result["samples_s"]), 2)

    def test_partial_writes_preserve_payload_and_count(self):
        left, right = socket.socketpair()
        try:
            left.setblocking(False)
            right.setblocking(False)

            class PartialWriter:
                def send(self, data):
                    return left.send(data[:7])

            payload = b"partial\x00\xff" * 50
            with selectors.DefaultSelector() as ready:
                ready.register(right, selectors.EVENT_READ, 0)
                self.assertEqual(workload.transfer([PartialWriter()], [right], ready, [payload], 3, False),
                                 len(payload) * 3)
        finally:
            left.close()
            right.close()

    def test_corrupted_bytes_fail_even_with_correct_total_length(self):
        left, right = socket.socketpair()
        try:
            class CorruptWriter:
                def send(self, data):
                    return left.send(b"!" + data[1:])

            with selectors.DefaultSelector() as ready:
                ready.register(right, selectors.EVENT_READ, 0)
                with self.assertRaisesRegex(AssertionError, "binary payload differs"):
                    workload.transfer([CorruptWriter()], [right], ready, [b"correct\x00\xff"], 1, False)
        finally:
            left.close()
            right.close()

    def test_premature_eof_does_not_count_as_completion(self):
        left, right = socket.socketpair()
        try:
            left.shutdown(socket.SHUT_WR)

            class MissingWriter:
                def send(self, data):
                    return len(data)

            with selectors.DefaultSelector() as ready:
                ready.register(right, selectors.EVENT_READ, 0)
                with self.assertRaisesRegex(AssertionError, "premature EOF"):
                    workload.transfer([MissingWriter()], [right], ready, [b"missing"], 1, False)
        finally:
            left.close()
            right.close()

    def test_wrong_checksum_and_missing_samples_are_rejected(self):
        for output in (b"first 64 100\nsample 63 100\n", b"first 64 100\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                benchmark.validate_measurement(output, "pair_64", 1, 0, 1)

    def test_failed_build_leaves_failed_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            with mock.patch.object(benchmark, "benchmark", side_effect=RuntimeError("build failed")), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(benchmark.main(["--json", str(path)]), 1)
            import json
            self.assertEqual(json.loads(path.read_text())["result"], "fail")

    @unittest.skipUnless(sys.platform == "linux" and Path("/proc/self/fd").exists(), "Linux fd count")
    def test_repeated_socket_consumers_release_descriptors(self):
        before = len(os.listdir("/proc/self/fd"))
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(4):
                workload.run("sparse_64", 1, 0, 1)
        self.assertEqual(len(os.listdir("/proc/self/fd")), before)


if __name__ == "__main__":
    unittest.main()
