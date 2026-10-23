"""Regression warning and evidence controls; no LLVM or timing-sensitive assertions."""
from pathlib import Path
import contextlib
import io
import os
import runpy
import sys
import unittest
from unittest import mock

import bench_pyperformance
import perf_smoke as perf


class KernelTests(unittest.TestCase):
    def load_graph(self):
        path, _ = perf.CASES["graph_copy"]
        with mock.patch.object(sys, "argv", [path, "typed", "1"]), \
                contextlib.redirect_stdout(io.StringIO()):
            return runpy.run_path(perf.ROOT / path)

    def test_graph_smoke_matches_historical_checksum_and_protocol(self):
        path, arguments = perf.CASES["graph_copy"]
        self.assertEqual(arguments, ["graph-smoke", "4000"])
        record = bench_pyperformance.run(
            [sys.executable, str(perf.ROOT / path), "graph-smoke", "3"],
            dict(os.environ), 10, "729753\n")
        self.assertGreaterEqual(record["loop_s"], 0)
        historical = bench_pyperformance.execute(
            [sys.executable, str(perf.ROOT / path), "graph", "3"], dict(os.environ), 10)
        fields = historical["stdout"].split()
        self.assertEqual(len(fields), 3)
        self.assertEqual(fields[0], record["stdout"].strip())
        self.assertTrue(all(int(value) >= 0 for value in fields[1:]))

    def test_graph_copy_preserves_cycles_and_shared_nodes(self):
        graph = self.load_graph()
        original = graph["build"](7)
        copied = graph["copy_value"](original, {})
        self.assertIsNot(copied, original)
        self.assertIs(copied.children[0].parent, copied)
        self.assertIs(copied.children[0].children[1].left, copied.children[0])
        self.assertIs(copied.children[0].payload, copied.children[2].payload)
        shared = copied.children[3]
        self.assertIs(shared.left, shared.right)
        self.assertIs(shared.left, copied.children[0].payload)
        self.assertIsNot(shared.left, original.children[3].left)
        registry = copied.children[4]
        self.assertIs(registry.entries["self"], registry)
        self.assertIs(registry.entries[None].value["deep"][1], copied)
        self.assertEqual(graph["checksum"](original, {}), graph["checksum"](copied, {}))

    def test_graph_timing_excludes_construction_and_includes_copy_and_checksum(self):
        graph_smoke = self.load_graph()["graph_smoke"]
        events = []

        def build(seed):
            events.append("build")
            return seed

        def copy(value, memo):
            events.append("copy")
            self.assertEqual(memo, {})
            return value

        def checksum(value, seen):
            events.append("checksum")
            self.assertEqual(seen, {})
            return value

        times = iter((2000000000, 5000000000))

        def clock():
            events.append("clock")
            return next(times)

        output, timing = io.StringIO(), io.StringIO()
        with mock.patch.dict(graph_smoke.__globals__, build=build, copy_value=copy,
                             checksum=checksum, process_time_ns=clock), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(timing):
            graph_smoke(2)
        self.assertEqual(events, ["build", "build", "clock", "copy", "checksum", "copy", "checksum", "clock"])
        self.assertEqual(output.getvalue(), "1\n")
        self.assertEqual(bench_pyperformance.seconds(timing.getvalue()), 3.0)

    def test_numeric_identity_cases_match_analytical_checksum_and_timing_protocol(self):
        for case, seed, expected in (("copy_int", "1", "int 6197\n"),
                                     ("copy_float", "4", "float 40\n"),
                                     ("global_int", "1", "global_int 6197\n"),
                                     ("global_float", "4", "global_float 40\n")):
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
        self.assertEqual(second["loop_clock"], "perf_counter")

    def test_graph_processing_records_cpu_clock_and_all_five_metrics(self):
        with mock.patch.object(perf, "execute", return_value=self.record()), \
                mock.patch.object(bench_pyperformance, "execute", return_value=self.record()):
            result = perf.measure("graph_copy", {"base": "base", "head": "head"},
                                  {"base": {}, "head": {}}, Path("/tmp/perf"), set())
        self.assertEqual(result["loop_clock"], "process_time_ns")
        self.assertEqual(set(result["comparison"]), set(perf.METRICS))


if __name__ == "__main__":
    unittest.main()
