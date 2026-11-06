"""Example benchmark evidence controls; no compiler or timing thresholds required."""
import ast
from contextlib import ExitStack, redirect_stdout
import csv
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import example_bench as bench

ROOT = Path(__file__).resolve().parents[1]
REPORT = b"2 unknown words in 3 lines\n"
LEGACY = ("column", "csvstat", "cut", "latency", "linediff", "mailmerge", "mazepath",
          "montecarlo", "suggest", "topk", "urlstats")


def load_example(name, filename="bench.py"):
    spec = importlib.util.spec_from_file_location(name + "_" + filename[:-3], ROOT / "examples" / name / filename)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "path", [str(ROOT / "examples" / name), *sys.path]):
        spec.loader.exec_module(module)
    return module


def rss_fields(output=REPORT, status=0, stderr=b"", rss=1024):
    return [rss, status, len(output), hashlib.sha256(output).hexdigest(), stderr.decode()]


def response(cmd, output=REPORT, status=0, stderr=b""):
    if bench.RSS_PROBE in cmd:
        return subprocess.CompletedProcess(cmd, 0, json.dumps(rss_fields(output, status, stderr)).encode(), b"")
    return subprocess.CompletedProcess(cmd, status, output, stderr)


class MeasurementTests(unittest.TestCase):
    def test_pairs_validate_before_timing_and_rotate_order(self):
        with mock.patch.object(bench, "execute", side_effect=lambda cmd, **_kwargs: response(cmd)) as run:
            results = bench.measure_pair([["cpython"], ["aot"]], 3)
        self.assertEqual([call.args[0][0] for call in run.call_args_list[:-2]],
                         ["cpython", "aot", "cpython", "aot", "aot", "cpython", "cpython", "aot"])
        for result in results:
            self.assertEqual(result.stdout, REPORT)
            self.assertEqual(result.rss_kib, 1024)
            self.assertGreater(result.wall_s, 0)
        self.assertTrue(all(call.kwargs["timeout"] > 0 for call in run.call_args_list))

    def test_every_warmup_timed_and_rss_output_is_checked(self):
        for timed in (False, True):
            # Oracle + native warm-up, optional timed warm-ups, three pairs, two RSS runs.
            for bad_run in range(12 if timed else 10):
                calls = 0

                def execute(cmd, bad_run=bad_run, **_kwargs):
                    nonlocal calls
                    output = b"wrong\n" if calls == bad_run else REPORT
                    calls += 1
                    stderr = b"read 0.125 s, report 0.000 s\n" if "--time" in cmd else b""
                    return response(cmd, output, stderr=stderr)

                options = {"timed_commands": [["cpython", "--time"], ["aot", "--time"]],
                           "timing_labels": ("read", "report"), "zero_ok": ("report",)} if timed else {}
                with self.subTest(timed=timed, bad_run=bad_run), \
                        mock.patch.object(bench, "execute", side_effect=execute), \
                        self.assertRaisesRegex(ValueError, "OUTPUT DIFFERS"):
                    bench.measure_pair([["cpython"], ["aot"]], 3, **options)

    def test_every_exit_status_and_diagnostic_is_checked_including_rss(self):
        for expected in (0, 1):
            for bad_run in range(6):
                for failure in ("status", "signal", "stderr"):
                    calls = 0

                    def execute(cmd, bad_run=bad_run, expected=expected, failure=failure, **_kwargs):
                        nonlocal calls
                        bad = calls == bad_run
                        calls += 1
                        code = (1 - expected if failure == "status" else -11) if bad and failure != "stderr" else expected
                        stderr = b"unexpected diagnostic\n" if bad and failure == "stderr" else b""
                        return response(cmd, status=code, stderr=stderr)

                    with self.subTest(expected=expected, bad_run=bad_run, failure=failure), \
                            mock.patch.object(bench, "execute", side_effect=execute), \
                            self.assertRaises((ValueError, RuntimeError)):
                        bench.measure_pair([["cpython"], ["aot"]], 1, status=expected)

    def test_fixed_stderr_must_match_in_every_sample_and_rss_run(self):
        expected = b"mailmerge: 100000 messages\n"
        for bad_run in range(6):
            for wrong in (b"", b"mailmerge: 99999 messages\n", expected + b"warning\n"):
                calls = 0

                def execute(cmd, bad_run=bad_run, wrong=wrong, **_kwargs):
                    nonlocal calls
                    stderr = wrong if calls == bad_run else expected
                    calls += 1
                    return response(cmd, stderr=stderr)

                with self.subTest(bad_run=bad_run, wrong=wrong), \
                        mock.patch.object(bench, "execute", side_effect=execute), \
                        self.assertRaisesRegex(ValueError, "unexpected stderr"):
                    bench.measure_pair([["cpython"], ["aot"]], 1, expected_stderr=expected)

    def test_invalid_sample_counts_fail_before_execution(self):
        for runs in (0, -1, True, 1.5, "1.5", "invalid"):
            with self.subTest(runs=runs), mock.patch.object(bench, "execute") as run, \
                    self.assertRaisesRegex(ValueError, "positive integer"):
                bench.measure_pair([["cpython"], ["aot"]], runs)
            run.assert_not_called()
        for commands, timed in (([], None), ([["cpython"], ["aot"]], [["cpython"]])):
            with self.subTest(commands=commands, timed=timed), \
                    mock.patch.object(bench, "execute") as run, self.assertRaises(ValueError):
                bench.measure_pair(commands, 1, timed_commands=timed)
            run.assert_not_called()

    def test_report_schema_and_every_number_are_validated(self):
        valid = "read 0.125 s, report 0.250 s\n"
        self.assertEqual(bench.parse_timings(valid, ("read", "report")), {"read": 0.125, "report": 0.25})
        invalid = ["", valid + "warning\n", valid + valid, valid.replace("report", "read"),
                   valid.replace(" s,", " seconds,"), valid.replace(", report 0.250 s", "")]
        for value in ("nan", "inf", "-inf", "0", "-0.5"):
            invalid += [valid.replace("0.125", value), valid.replace("0.250", value)]
        for report in invalid:
            with self.subTest(report=report), self.assertRaises(ValueError):
                bench.parse_timings(report, ("read", "report"))
        self.assertEqual(bench.parse_timings("read 1 s, report 0 s", ("read", "report"),
                                             zero_ok=("report",))["report"], 0)
        with self.assertRaises(ValueError):
            bench.parse_timings("read 0 s, report 0 s", ("read", "report"), zero_ok=("report",))

    def test_nonfinite_or_nonpositive_wall_and_cpu_samples_fail(self):
        for value in (0, -1, float("nan"), float("inf")):
            for cpu in (False, True):
                with self.subTest(value=value, cpu=cpu), \
                        mock.patch.object(bench, "execute", side_effect=lambda cmd, **_kwargs: response(cmd)), \
                        mock.patch.object(bench.time, "perf_counter", side_effect=[0, 1 if cpu else value]), \
                        mock.patch.object(bench, "child_cpu", side_effect=[0, value]), \
                        self.assertRaisesRegex(ValueError, "finite and positive"):
                    bench.run(["aot"], cpu=cpu)

    def test_rss_schema_and_units(self):
        for field, value in ((0, 0), (0, -1), (0, True), (0, 1.5), (1, True), (2, True),
                             (2, len(REPORT) + 1), (3, "bad digest"), (4, 0)):
            fields = rss_fields()
            fields[field] = value
            result = subprocess.CompletedProcess([], 0, json.dumps(fields).encode(), b"")
            with self.subTest(field=field, value=value), \
                    mock.patch.object(bench, "execute", return_value=result), \
                    self.assertRaises((ValueError, RuntimeError)):
                bench.peak_rss(["aot"], REPORT)
        for raw in ({}, [], rss_fields()[:-1], rss_fields() + [0]):
            result = subprocess.CompletedProcess([], 0, json.dumps(raw).encode(), b"")
            with self.subTest(raw=raw), mock.patch.object(bench, "execute", return_value=result), \
                    self.assertRaisesRegex(ValueError, "invalid RSS report"):
                bench.peak_rss(["aot"], REPORT)
        result = subprocess.CompletedProcess([], 0, json.dumps(rss_fields(rss=1048576)).encode(), b"")
        with mock.patch.object(bench, "execute", return_value=result):
            for platform, expected in (("linux", 1048576), ("darwin", 1024)):
                with self.subTest(platform=platform), mock.patch.object(bench.sys, "platform", platform):
                    self.assertEqual(bench.peak_rss(["aot"], REPORT), expected)

    def test_real_status_stderr_rss_and_timeout_controls(self):
        command = [sys.executable, "-I", "-c", "import sys; print('reference'); sys.exit(1)"]
        self.assertEqual(bench.run(command, status=1).stdout, b"reference\n")
        self.assertGreater(bench.peak_rss(command, b"reference\n", status=1), 0)
        with self.assertRaisesRegex(RuntimeError, "exit 1, expected 0"):
            bench.run(command)
        with self.assertRaisesRegex(RuntimeError, "exit 1, expected 0"):
            bench.peak_rss(command, b"reference\n")
        noisy = [sys.executable, "-I", "-c", "import sys; print('warning', file=sys.stderr)"]
        with self.assertRaisesRegex(ValueError, "unexpected stderr"):
            bench.run(noisy)
        sleeper = [sys.executable, "-I", "-c", "import time; time.sleep(60)"]
        with self.assertRaises(subprocess.TimeoutExpired):
            bench.run(sleeper, timeout=0.05)
        with self.assertRaises(subprocess.TimeoutExpired):
            bench.peak_rss(sleeper, b"", timeout=0.05)

    def test_timeout_releases_a_grandchilds_resources(self):
        # A direct-child-only kill leaves its child's inherited stderr pipe and
        # lock open. Checking the lock also works when the dead child is a zombie.
        import fcntl
        child = ("import fcntl, sys, time; f = open(sys.argv[1], 'w'); "
                 "fcntl.flock(f, fcntl.LOCK_EX); print('ready', flush=True); time.sleep(60)")
        parent = ("import subprocess, sys, time; "
                  "p = subprocess.Popen([sys.executable, '-I', '-c', sys.argv[1], sys.argv[2]], "
                  "stdout=subprocess.PIPE); print(p.stdout.readline().decode().strip(), flush=True); time.sleep(60)")
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "child.lock"
            command = [sys.executable, "-I", "-c", parent, child, str(lock)]
            with self.assertRaises(subprocess.TimeoutExpired) as failure:
                bench.run(command, timeout=2)
            self.assertIn(b"ready", failure.exception.output)
            with lock.open() as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_real_mailmerge_stderr_is_validated_instead_of_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            template, data = Path(directory) / "notice.txt", Path(directory) / "people.tsv"
            template.write_text("Hello $name, message $seq/$count.\n")
            data.write_text("name\nAda\nGrace\n")
            command = [sys.executable, "-I", str(ROOT / "examples/mailmerge/mailmerge.py"),
                       str(template), str(data)]
            expected = b"mailmerge: 2 messages\n"
            result = bench.run(command, expected_stderr=expected)
            self.assertIn(b"Hello Ada, message 1/2.", result.stdout)
            self.assertGreater(bench.peak_rss(command, result.stdout, expected_stderr=expected), 0)
            with self.assertRaisesRegex(ValueError, "unexpected stderr"):
                bench.run(command, expected_stderr=b"mailmerge: 1 messages\n")


class LegacyCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = {name: load_example(name) for name in LEGACY}

    def invoke(self, name, corrupt=False):
        module = self.modules[name]
        native_calls = 0

        def execute(cmd, **_kwargs):
            nonlocal native_calls
            if "build" in cmd:
                return response(cmd, b"")
            status = 1 if name in ("suggest", "linediff") else 0
            output = REPORT
            if str(cmd[0]).endswith("_aot"):
                native_calls += 1
                # Only an intermediate result differs; later results would agree.
                if corrupt and native_calls == 2:
                    output = b"wrong\n"
            stderr = b"mailmerge: 100000 messages\n" if name == "mailmerge" else b""
            if "--time" in cmd:
                labels = {"topk": ("count", "pick"), "latency": ("read", "statistics"),
                          "urlstats": ("read", "report")}[name]
                stderr = f"{labels[0]} 0.125 s, {labels[1]} 0.250 s\n".encode()
            return response(cmd, output, status, stderr)

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", [module.__file__, "fake-compiler", "2"]))
            stack.enter_context(mock.patch.object(module.os, "makedirs"))
            stack.enter_context(mock.patch.object(module.os.path, "exists", return_value=True))
            stack.enter_context(mock.patch.object(module.os.path, "getsize", return_value=100))
            stack.enter_context(mock.patch.object(bench, "child_cpu", side_effect=itertools.count()))
            process = stack.enter_context(mock.patch.object(bench, "execute", side_effect=execute))
            if name == "csvstat":
                stack.enter_context(mock.patch.object(module, "per_row", return_value=[[1, 2, 3], [1, 2, 3]]))
            output = stack.enter_context(redirect_stdout(io.StringIO()))
            module.main()
            self.assertTrue(all(call.kwargs["timeout"] > 0 for call in process.call_args_list))
        return output.getvalue()

    def test_all_eleven_cli_paths_keep_reporting_valid_results(self):
        for name in LEGACY:
            with self.subTest(name=name):
                output = self.invoke(name)
                self.assertIn("speedup", output)
                self.assertNotIn("OUTPUT DIFFERS", output)

    def test_all_eleven_cli_paths_fail_on_an_intermediate_wrong_output(self):
        for name in LEGACY:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "OUTPUT DIFFERS"):
                self.invoke(name, corrupt=True)

    def test_invalid_run_count_never_builds_or_generates_inputs(self):
        for name, module in self.modules.items():
            with self.subTest(name=name), mock.patch.object(sys, "argv", [module.__file__, "compiler", "0"]), \
                    mock.patch.object(bench, "execute") as run, self.assertRaises(ValueError):
                module.main()
            run.assert_not_called()


class CsvEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_example("csvstat")
        cls.rwbench = load_example("csvstat", "rwbench.py")

    REPORT = b"3 rows, read back as written\nread 1.000 us/row, parse 2.000 us/row, write 3.000 us/row\n"

    def test_roundtrip_report_and_all_three_metrics_are_required(self):
        self.assertEqual(self.module.rwbench_timings(self.REPORT, 3), {"read": 1, "parse": 2, "write": 3})
        invalid = [b"", self.REPORT.replace(b"3 rows", b"2 rows"), self.REPORT.replace(b"as written", b"DIFFERENT"),
                   self.REPORT + b"warning\n", self.REPORT.replace(b", parse 2.000 us/row", b"")]
        for label in (b"1.000", b"2.000", b"3.000"):
            invalid += [self.REPORT.replace(label, value) for value in (b"nan", b"inf", b"0", b"-1")]
        for report in invalid:
            with self.subTest(report=report), self.assertRaises(ValueError):
                self.module.rwbench_timings(report, 3)

    def test_each_written_copy_is_compared_with_cpython(self):
        for bad_run in range(6):
            with self.subTest(bad_run=bad_run), tempfile.TemporaryDirectory() as directory:
                copy = Path(directory) / "copy.csv"
                calls = 0

                def execute(cmd, copy=copy, bad_run=bad_run, **_kwargs):
                    nonlocal calls
                    copy.write_bytes(b"wrong\n" if calls == bad_run else b"a,b\n1,2\n3,4\n")
                    calls += 1
                    return response(cmd, self.REPORT)

                with mock.patch.object(bench, "execute", side_effect=execute), \
                        self.assertRaisesRegex(ValueError, "CSV copy differs"):
                    self.module.per_row([["cpython"], ["aot"]], 2, 3, copy)

    def test_missing_write_cannot_reuse_a_previous_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "copy.csv"
            copy.write_bytes(b"previous successful output")
            with mock.patch.object(bench, "execute", return_value=response([], self.REPORT)), \
                    self.assertRaises(FileNotFoundError):
                self.module.per_row([["cpython"], ["aot"]], 1, 3, copy)

    def test_roundtrip_program_itself_fails_on_a_parse_disagreement(self):
        with tempfile.TemporaryDirectory() as directory:
            source, copy = Path(directory) / "source.csv", Path(directory) / "copy.csv"
            source.write_text("a\n")
            with mock.patch.object(sys, "argv", ["rwbench.py", str(source), str(copy)]), \
                    mock.patch.object(csv, "reader", side_effect=[[["a"]], [["wrong"]]]), \
                    self.assertRaisesRegex(ValueError, "results differ"):
                self.rwbench.main()


class NdarrayEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_example("ndarray")

    def report(self, checksum="2.5"):
        return ("".join(f"{label}\t1.000\n" for label in self.module.LABELS) + f"checksum\t{checksum}\n").encode()

    def test_expected_labels_match_the_actual_workload(self):
        tree = ast.parse((ROOT / "examples/ndarray/workloads.py").read_text())
        labels = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "LABELS" for target in node.targets))
        self.assertEqual(tuple(ast.literal_eval(labels)), self.module.LABELS)

    def test_missing_duplicate_extra_and_invalid_rows_or_checksums_fail(self):
        report = self.report()
        rows = report.splitlines(keepends=True)
        invalid = [b"", b"checksum\t2.5\n", b"".join(rows[1:]), b"".join([rows[0], *rows]),
                   b"".join([rows[0], rows[0], *rows[2:]]), report + b"extra\t1\n",
                   report.replace(b"checksum", b"missing"), self.report("nan"), self.report("inf")]
        invalid += [report.replace(b"\t1.000\n", b"\t" + value + b"\n", 1)
                    for value in (b"nan", b"inf", b"0", b"-1")]
        for output in invalid:
            with self.subTest(output=output), mock.patch.object(bench, "execute", return_value=response([], output)), \
                    self.assertRaises(ValueError):
                self.module.timings(["aot"])
        with mock.patch.object(bench, "execute", return_value=response([], report)):
            ms, checksum = self.module.timings(["aot"], "2.5")
            self.assertEqual((len(ms), checksum), (15, "2.5"))
            with self.assertRaisesRegex(ValueError, "differs from CPython"):
                self.module.timings(["aot"], "3.5")

    def test_same_native_error_cannot_pass_without_cpython_agreement(self):
        calls = []

        def execute(cmd, **_kwargs):
            calls.append(cmd)
            if cmd[0] == sys.executable:
                return response(cmd, self.report("2.5"))
            if "build" in cmd:
                return response(cmd, b"")
            return response(cmd, self.report("3.5"))

        with mock.patch.object(sys, "argv", ["bench.py", "compiler", "100", "2"]), \
                mock.patch.object(self.module.os, "makedirs"), \
                mock.patch.object(bench, "execute", side_effect=execute), \
                redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "differs from CPython"):
            self.module.main()
        self.assertEqual(calls[0][:3], [sys.executable, "-I", "-c"])
        self.assertEqual(calls[0][-2:], ["100", "2"])
        self.assertEqual(calls[1][1], "build")
        self.assertEqual(len(calls), 3)

    def test_invalid_dimensions_or_repetitions_fail_before_execution(self):
        for args in (("0", "2"), ("1", "2"), ("2", "0"), ("2", "-1")):
            with self.subTest(args=args), mock.patch.object(sys, "argv", ["bench.py", "compiler", *args]), \
                    mock.patch.object(bench, "execute") as run, self.assertRaises(ValueError):
                self.module.main()
            run.assert_not_called()


class NdarraySampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_example("ndarray", "workloads.py")

    def invoke(self, values, n=2, reps=3):
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", ["workloads.py", str(n), str(reps)]))
            stack.enter_context(mock.patch.object(self.module, "items", return_value=[0.0, 0.0]))
            stack.enter_context(mock.patch.object(self.module, "NDArray", return_value=object()))
            stack.enter_context(mock.patch.object(self.module, "zeros", return_value=object()))
            work = stack.enter_context(mock.patch.object(self.module, "run", return_value=1.0))
            stack.enter_context(mock.patch.object(self.module.time, "perf_counter", side_effect=values))
            output = stack.enter_context(redirect_stdout(io.StringIO()))
            self.module.main()
        return output.getvalue(), work.call_count

    def test_every_raw_elapsed_sample_is_checked_before_minimum(self):
        count = len(self.module.LABELS) * 3
        for bad_sample in (0, 1, 2, count - 1):
            for elapsed in (0.0, -1.0, float("nan"), float("inf"), -float("inf")):
                values = [value for _ in range(count) for value in (0.0, 1.0)]
                values[bad_sample * 2 + 1] = elapsed
                with self.subTest(sample=bad_sample, elapsed=elapsed), \
                        self.assertRaisesRegex(ValueError, "timing must be finite and positive"):
                    self.invoke(values)
        output, calls = self.invoke([value for _ in range(count) for value in (0.0, 1.0)])
        self.assertEqual(calls, count)
        self.assertEqual(len(output.splitlines()), len(self.module.LABELS) + 1)
        self.assertTrue(output.endswith("checksum\t45.0\n"))

    def test_empty_repetitions_cannot_publish_the_sentinel_as_a_time(self):
        for n, reps in ((0, 3), (1, 3), (2, 0), (2, -1)):
            with self.subTest(n=n, reps=reps), self.assertRaisesRegex(ValueError, "N must be at least 2"):
                self.invoke([], n, reps)

    def test_tiny_positive_samples_survive_the_producer_and_consumer(self):
        consumer = load_example("ndarray")
        count = len(self.module.LABELS)
        for elapsed in (1e-7, 1e-9, 1e-12):
            with self.subTest(elapsed=elapsed):
                output, calls = self.invoke([value for _ in range(count) for value in (0.0, elapsed)], reps=1)
                self.assertEqual(calls, count)
                with mock.patch.object(bench, "execute", return_value=response([], output.encode())):
                    timings, checksum = consumer.timings(["aot"], "15.0")
                self.assertEqual(checksum, "15.0")
                self.assertEqual(len(timings), count)
                for value in timings.values():
                    self.assertGreater(float(value), 0)
                    self.assertAlmostEqual(float(value) / (elapsed * 1000), 1.0)

    def test_numpy_display_also_preserves_tiny_positive_samples(self):
        consumer = load_example("ndarray")
        with mock.patch.dict(sys.modules, {"numpy": mock.MagicMock()}), \
                mock.patch.object(consumer.time, "perf_counter", side_effect=[0.0, 1e-9] * 11):
            timings = consumer.numpy_timings(2, 1)
        self.assertEqual(len(timings), 11)
        for value in timings.values():
            self.assertGreater(float(value), 0)
            self.assertAlmostEqual(float(value) / 1e-6, 1.0)


if __name__ == "__main__":
    unittest.main()
