"""Regression warning and evidence controls; no LLVM or timing-sensitive assertions."""
from pathlib import Path
import os
import sys
import unittest
from unittest import mock

import bench_pyperformance
import perf_smoke as perf


class KernelTests(unittest.TestCase):
    def test_numeric_copy_cases_match_analytical_checksum_and_timing_protocol(self):
        for case, seed, expected in (("copy_int", "1", "int 6197\n"),
                                     ("copy_float", "4", "float 40\n")):
            with self.subTest(case=case):
                path, arguments = perf.CASES[case]
                record = bench_pyperformance.run(
                    [sys.executable, str(perf.ROOT / path), arguments[0], "3", seed],
                    dict(os.environ), 10, expected)
                self.assertGreaterEqual(record["loop_s"], 0)


class ComparisonTests(unittest.TestCase):
    def test_threshold_and_absolute_floor(self):
        self.assertTrue(perf.compare([0.1] * 3, [0.12] * 3)["candidate"])
        self.assertTrue(perf.compare([0.025] * 3, [0.030] * 3)["candidate"])
        self.assertFalse(perf.compare([1.0] * 3, [1.1999] * 3)["candidate"])
        self.assertFalse(perf.compare([0.01] * 3, [0.014] * 3)["candidate"])

    def test_outlier_and_speedup_do_not_warn(self):
        for head in ([1.0, 1.0, 10.0], [0.7, 0.8, 0.9]):
            self.assertEqual(perf.classify(perf.compare([1.0] * 3, head), None), "ok")

    def test_invalid_samples_fail_closed(self):
        for invalid in ([], [1.0], [1.0] * 4, [0.0, 1.0, 1.0], [-1.0, 1.0, 1.0],
                        [float("nan"), 1.0, 1.0], [float("inf"), 1.0, 1.0]):
            for base, head in ((invalid, [1.0] * 3), ([1.0] * 3, invalid)):
                with self.subTest(base=base, head=head), self.assertRaises(ValueError):
                    perf.compare(base, head)

    def test_warning_requires_independent_confirmation(self):
        slowdown = perf.compare([1.0, 1.01, 1.02], [1.3, 1.31, 1.32])
        self.assertEqual(perf.classify(slowdown, None), "unconfirmed")
        self.assertEqual(perf.classify(slowdown, perf.compare([1.0] * 3, [1.1] * 3)), "unconfirmed")
        self.assertEqual(perf.classify(slowdown, perf.compare([2.0] * 3, [2.6] * 3)), "warning")

    def test_overlap_in_either_batch_is_unconfirmed(self):
        clean = perf.compare([1.0] * 3, [1.3] * 3)
        noisy = perf.compare([1.0, 1.0, 1.4], [1.3, 1.3, 1.5])
        self.assertTrue(noisy["candidate"])
        self.assertEqual(perf.classify(noisy, clean), "unconfirmed")
        self.assertEqual(perf.classify(clean, noisy), "unconfirmed")


class BatchTests(unittest.TestCase):
    def batch(self, offset=0):
        return perf.batch(Path("work.py"), ["2"], {"base": "base", "head": "head"},
                          {"base": {}, "head": {}}, Path("/tmp/perf"), "42\n", offset)

    def record(self, output="42\n"):
        return {"stdout": output, "stderr": "seconds 0.5\n", "wall_s": 1.0, "returncode": 0}

    def test_complete_samples_and_reversed_order_for_confirmation(self):
        for offset, order in ((0, ["base", "head", "head", "base", "base", "head"]),
                              (3, ["head", "base", "base", "head", "head", "base"])):
            with mock.patch.object(perf, "execute", return_value=self.record()) as builds, \
                    mock.patch.object(bench_pyperformance, "execute", return_value=self.record()):
                samples = self.batch(offset)
            self.assertEqual([call.args[0][0] for call in builds.call_args_list], order)
            self.assertEqual(len(samples["cpython"]), 3)
            for side in ("base", "head"):
                self.assertEqual(set(samples[side]), set(perf.METRICS))
                self.assertTrue(all(len(values) == 3 for values in samples[side].values()))

    def test_cpython_jit_and_aot_output_mismatches_abort(self):
        for failure_index in (0, 1, 2):
            records = [self.record() for _ in range(failure_index)] + [self.record("wrong\n")]
            with self.subTest(failure_index=failure_index), \
                    mock.patch.object(perf, "execute", return_value=self.record()), \
                    mock.patch.object(bench_pyperformance, "execute", side_effect=records), \
                    self.assertRaisesRegex(ValueError, "output differs"):
                self.batch()

    def test_build_failure_aborts(self):
        with mock.patch.object(perf, "execute", side_effect=RuntimeError("compiler failed")), \
                mock.patch.object(bench_pyperformance, "execute", return_value=self.record()), \
                self.assertRaisesRegex(RuntimeError, "compiler failed"):
            self.batch()

    def test_modes_reuse_binary_but_still_measure_and_validate_execution(self):
        built = set()
        compilers, envs = {"base": "base", "head": "head"}, {"base": {}, "head": {}}
        with mock.patch.object(perf, "execute", return_value=self.record()) as builds, \
                mock.patch.object(bench_pyperformance, "execute", return_value=self.record()) as runs:
            first = perf.measure("autograd", compilers, envs, Path("/tmp/perf"), built)
            self.assertEqual(builds.call_count, 8)  # two warm builds plus three pairs
            runs.reset_mock()
            second = perf.measure("numeric", compilers, envs, Path("/tmp/perf"), built)
            self.assertEqual(builds.call_count, 8)
        self.assertIn("build_s", first["comparison"])
        self.assertNotIn("build_s", second["comparison"])
        self.assertEqual(runs.call_count, 20)  # oracle, four warm runs, three CPython/JIT/AOT pairs
        self.assertEqual(set(second["comparison"]), set(perf.METRICS[1:]))


if __name__ == "__main__":
    unittest.main()
