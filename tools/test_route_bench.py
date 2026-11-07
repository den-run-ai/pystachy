"""Router benchmark failure paths; no LLVM required."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location("route_bench", Path(__file__).resolve().parents[1] / "examples/route/bench.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)


class PairedMeasurementTests(unittest.TestCase):
    def report(self, cmd, **_kwargs):
        return subprocess.CompletedProcess(cmd, 0, b"100 events, 1 rules\n      100 dest\n",
                                           b"routing: 0.1000 s, 1000000.0 ns per event\n" if "--in-memory" in cmd else b"")

    def test_alternating_pairs_keep_every_raw_round(self):
        with mock.patch.object(bench.checked, "execute", side_effect=self.report) as run:
            samples = bench.measure_pair([["cpython"], ["aot"]], 3, 100)
        self.assertEqual([call.args[0][0] for call in run.call_args_list],
                         ["cpython", "cpython", "aot", "aot",
                          "cpython", "cpython", "aot", "aot", "aot", "aot", "cpython", "cpython",
                          "cpython", "cpython", "aot", "aot"])
        for sample in samples:
            self.assertEqual(len(sample["wall_s"]), 3)
            self.assertEqual(sample["routing_s"], [0.1, 0.1, 0.1])

    def test_mismatch_in_every_execution_is_fatal(self):
        # Each streaming/in-memory run, runtime and repetition must agree, including a
        # discrepancy that appears in both runtimes rather than only the last report.
        for bad_run in range(12):
            calls = 0

            def differing(cmd, bad_run=bad_run, **kwargs):
                nonlocal calls
                result = self.report(cmd, **kwargs)
                if calls == bad_run:
                    result.stdout = result.stdout.replace(b"100 dest", b"99 dest")
                calls += 1
                return result

            with self.subTest(bad_run=bad_run), mock.patch.object(bench.checked, "execute", side_effect=differing):
                with self.assertRaisesRegex(ValueError, "OUTPUT DIFFERS"):
                    bench.measure_pair([["cpython"], ["aot"]], 2, 100)

    def test_wrong_trace_length_is_fatal(self):
        with mock.patch.object(bench.checked, "execute", side_effect=self.report):
            with self.assertRaisesRegex(ValueError, "event count"):
                bench.measure_pair([["cpython"], ["aot"]], 1, 101)

    def test_invalid_run_count_is_rejected_before_running(self):
        for runs in [0, -1]:
            with self.subTest(runs=runs), mock.patch.object(bench.checked, "execute") as run:
                with self.assertRaisesRegex(ValueError, "positive"):
                    bench.measure_pair([["cpython"], ["aot"]], runs, 100)
                run.assert_not_called()

    def test_malformed_or_zero_routing_time_is_fatal(self):
        for report in ["", "routing: nan s, 1 ns per event", "routing: -1 s, 1 ns per event",
                       "routing: 0.0000 s, 0.0 ns per event", "routing: 1 s, 1 ns per event\nwarning",
                       "routing: 1 s, nan ns per event", "routing: 1 s, inf ns per event",
                       "routing: 1 s, -1 ns per event", "routing: 1 s, 0 ns per event"]:
            with self.subTest(report=report), self.assertRaises(ValueError):
                bench.routing_time(report)

    def test_both_rounded_durations_must_describe_the_same_work(self):
        self.assertEqual(bench.routing_time("routing: 0.1000 s, 1000000.0 ns per event", 100), 0.1)
        # Both rounded fields can differ slightly without contradicting each other.
        self.assertEqual(bench.routing_time("routing: 0.1000 s, 1000000.1 ns per event", 100), 0.1)
        with self.assertRaisesRegex(ValueError, "inconsistent routing durations"):
            bench.routing_time("routing: 0.1000 s, 1.0 ns per event", 100)

    def test_rss_without_reference_checks_the_following_run_against_it(self):
        report = b"100 events, 1 rules\n      100 dest\n"
        oracle = subprocess.CompletedProcess([], 0, report, b"")
        rss = subprocess.CompletedProcess([], 0,
                                          json.dumps([1024, 0, len(report), hashlib.sha256(report).hexdigest(), ""]).encode(), b"")
        with mock.patch.object(bench.checked, "execute", side_effect=[oracle, rss]):
            self.assertEqual(bench.peak_rss(["cpython", "--names"]), (1024, report.decode()))

    def test_process_failure_is_not_treated_as_a_timing_sample(self):
        with mock.patch.object(bench.checked, "execute", side_effect=subprocess.CalledProcessError(1, ["aot"])):
            with self.assertRaises(subprocess.CalledProcessError):
                bench.measure_pair([["cpython"], ["aot"]], 1, 100)

    def test_rss_output_mismatch_and_diagnostics_are_fatal(self):
        for report, stderr in [("different", ""), ("expected", "warning")]:
            result = subprocess.CompletedProcess([], 0, json.dumps([1024, 0, len(report), hashlib.sha256(report.encode()).hexdigest(), stderr]).encode(), b"")
            with self.subTest(report=report, stderr=stderr), mock.patch.object(bench.checked, "execute", return_value=result):
                with self.assertRaises(ValueError):
                    bench.peak_rss(["aot", "--names"], expected="expected")

    def test_rss_units_follow_host_platform(self):
        result = subprocess.CompletedProcess([], 0, json.dumps([1048576, 0, 8, hashlib.sha256(b"expected").hexdigest(), ""]).encode(), b"")
        with mock.patch.object(bench.checked, "execute", return_value=result):
            with mock.patch.object(bench.sys, "platform", "linux"):
                self.assertEqual(bench.peak_rss(["aot"], expected="expected"), (1048576, "expected"))
            with mock.patch.object(bench.sys, "platform", "darwin"):
                self.assertEqual(bench.peak_rss(["aot"], expected="expected"), (1024, "expected"))

    def test_provenance_uses_compiler_toolchain_discovery(self):
        # A Homebrew/apt installation need not expose an unversioned clang on PATH.
        selected = "/opt/homebrew/opt/llvm@20/bin"

        def run(cmd, **kwargs):
            if cmd[0] == "git":
                return subprocess.CompletedProcess(cmd, 0, b"revision\n", b"")
            if "-c" in cmd:
                return subprocess.CompletedProcess(cmd, 0, (selected + "\n").encode(), b"")
            if cmd == [selected + "/clang", "--version"]:
                return subprocess.CompletedProcess(cmd, 0, b"Homebrew clang version 20.1.8\n", b"")
            raise FileNotFoundError(cmd[0])

        with mock.patch.object(bench.checked, "execute", side_effect=run):
            data = bench.provenance(Path.cwd(), "pystachy", [])
        self.assertEqual(data["clang"], "Homebrew clang version 20.1.8")


if __name__ == "__main__":
    unittest.main()
