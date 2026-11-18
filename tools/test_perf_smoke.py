"""Regression warning and evidence controls; no LLVM or timing-sensitive assertions."""
from pathlib import Path
import contextlib
import io
import json
import os
import runpy
import signal
import subprocess
import sys
import tempfile
import textwrap
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

    def test_dynamic_iteration_checksums_work_counts_and_timing_protocol(self):
        # These newly supported paths cannot yet be base/head timing cases: the
        # base compiler rejects them. Keep their deterministic workload checks.
        path = perf.ROOT / "tools/dynany_iteration_bench.py"
        for n in (0, 1, 17):
            for kind in ("list", "range", "object", "generator"):
                advances = n + 1 if kind in ("object", "generator") else 0
                expected = f"{kind} {n * (n - 1) // 2} {n} {advances}\n"
                with self.subTest(kind=kind, n=n):
                    record = bench_pyperformance.run(
                        [sys.executable, str(path), kind, str(n), "smoke"],
                        dict(os.environ), 10, expected)
                    self.assertGreaterEqual(record["loop_s"], 0)

    def test_dynamic_iteration_rejects_eager_production(self):
        path = perf.ROOT / "tools/dynany_iteration_bench.py"
        with mock.patch.object(sys, "argv", [str(path), "list", "0"]), \
                contextlib.redirect_stdout(io.StringIO()):
            workload = runpy.run_path(path)
        steps = workload["Steps"]()
        eager = list(workload["generated"](3, steps))
        with self.assertRaises(AssertionError):
            workload["consume"](eager, steps, True)

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


class ReportTests(unittest.TestCase):
    def result(self, name):
        return {"name": name, "samples": {"base": [0.1, 0.2, 0.3]},
                "confirmation": {"head": [0.4, 0.5, 0.6]}, "comparison": {}}

    @contextlib.contextmanager
    def main_context(self, path, measure=None, execute=None):
        record = {"stdout": "revision\n", "stderr": "", "wall_s": 1.0, "returncode": 0}
        env = {key: value for key, value in os.environ.items() if key != "GITHUB_STEP_SUMMARY"}
        with mock.patch.object(sys, "argv", ["perf_smoke.py", "--base", str(path.parent), "--json", str(path)]), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(perf, "CASES", {"first": None, "second": None}), \
                mock.patch.object(perf, "execute", side_effect=execute, return_value=record), \
                mock.patch.object(perf, "measure", side_effect=measure or (lambda name, *args: self.result(name))), \
                mock.patch.object(perf.os, "sched_getaffinity", return_value={0, 1}), \
                mock.patch.object(perf.os, "sched_setaffinity"), \
                contextlib.redirect_stdout(io.StringIO()):
            yield

    def test_complete_report_preserves_finished_workload_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            finished = []

            def measure(name, compilers, environments, *args):
                checkpoint = json.loads(path.read_text())
                self.assertEqual(checkpoint["status"], "incomplete")
                self.assertEqual(checkpoint["phase"], f"measure:{name}")
                self.assertEqual(checkpoint["results"], finished)
                self.assertEqual(set(checkpoint["bootstrap"]), {"base", "head"})
                self.assertEqual(checkpoint["environment"]["PYSTACHY_PROGRAM_CACHE"], "0")
                self.assertEqual({side: env["PYSTACHY_PROGRAM_CACHE"] for side, env in environments.items()},
                                 {"base": "0", "head": "0"})
                finished.append(self.result(name))
                return finished[-1]

            with mock.patch.dict(os.environ, PYSTACHY_PROGRAM_CACHE="1"), self.main_context(path, measure):
                perf.main()
            report = json.loads(path.read_text())
            self.assertEqual(report["schema"], 2)
            self.assertEqual((report["status"], report["phase"]), ("complete", "complete"))
            self.assertEqual(report["results"], finished)
            self.assertEqual(len(finished), 2)
            self.assertNotIn("error", report)

    def test_bootstrap_failure_retains_the_completed_bootstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            builds = 0

            def execute(command, env, timeout):
                nonlocal builds
                checkpoint = json.loads(path.read_text())
                self.assertEqual(checkpoint["status"], "incomplete")
                if "build" in command:
                    builds += 1
                    if builds == 2:
                        self.assertEqual(set(checkpoint["bootstrap"]), {"base"})
                        raise RuntimeError("head bootstrap failed")
                return {"stdout": "revision\n", "wall_s": 1.0}

            with self.main_context(path, execute=execute), self.assertRaisesRegex(RuntimeError, "head bootstrap failed"):
                perf.main()
            report = json.loads(path.read_text())
            self.assertEqual((report["status"], report["phase"]), ("error", "bootstrap:head"))
            self.assertEqual(report["error"], "head bootstrap failed")
            self.assertEqual(report["error_type"], "RuntimeError")
            self.assertEqual(set(report["bootstrap"]), {"base"})
            self.assertEqual(report["results"], [])

    def test_setup_failure_writes_an_error_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with self.main_context(path), \
                    mock.patch.object(perf.os, "sched_getaffinity", side_effect=OSError("affinity unavailable")), \
                    self.assertRaisesRegex(OSError, "affinity unavailable"):
                perf.main()
            report = json.loads(path.read_text())
            self.assertEqual((report["status"], report["phase"]), ("error", "setup"))
            self.assertEqual(report["results"], [])

    def test_workload_errors_and_interrupts_keep_completed_samples(self):
        for failure in (ValueError("output differs"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "report.json"
                first = self.result("first")
                with self.main_context(path, measure=[first, failure]), self.assertRaises(type(failure)):
                    perf.main()
                report = json.loads(path.read_text())
                self.assertEqual((report["status"], report["phase"]), ("error", "measure:second"))
                self.assertEqual(report["error"], str(failure))
                self.assertEqual(report["error_type"], type(failure).__name__)
                self.assertEqual(report["results"], [first])

    def test_summary_failure_does_not_publish_complete_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with self.main_context(path), mock.patch.object(perf, "summary", side_effect=ValueError("summary failed")), \
                    self.assertRaisesRegex(ValueError, "summary failed"):
                perf.main()
            report = json.loads(path.read_text())
            self.assertEqual((report["status"], report["phase"]), ("error", "summary"))
            self.assertEqual(report["results"], [self.result("first"), self.result("second")])

    def test_checkpoint_failure_still_restores_cpu_affinity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            original_write = perf.write_report

            def write_report(path, report):
                if "affinity" in report:
                    raise OSError("checkpoint write failed")
                original_write(path, report)

            with self.main_context(path), mock.patch.object(perf, "write_report", side_effect=write_report), \
                    mock.patch.object(perf.os, "sched_setaffinity") as affinity, \
                    self.assertRaisesRegex(OSError, "checkpoint write failed"):
                perf.main()
            self.assertEqual(affinity.call_args_list, [mock.call(0, {0}), mock.call(0, [0, 1])])
            self.assertEqual(json.loads(path.read_text())["status"], "incomplete")

    def test_sigterm_leaves_a_valid_incomplete_checkpoint_without_finally(self):
        code = textwrap.dedent("""
            import os
            import signal
            from unittest import mock
            import perf_smoke as perf

            def measure(name, *args):
                if name == "second":
                    os.kill(os.getpid(), signal.SIGTERM)
                return {"name": name, "samples": {"base": [1, 2, 3]},
                        "confirmation": {"head": [4, 5, 6]}, "comparison": {}}

            with mock.patch.object(perf, "CASES", {"first": None, "second": None}), \\
                    mock.patch.object(perf, "execute", return_value={"stdout": "revision", "wall_s": 1}), \\
                    mock.patch.object(perf, "measure", side_effect=measure):
                perf.main()
        """)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            env = dict(os.environ, PYTHONPATH=str(Path(perf.__file__).parent), TMPDIR=directory)
            process = subprocess.run([sys.executable, "-c", code, "--base", directory, "--json", str(path)],
                                     env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, -signal.SIGTERM, process.stderr)
            report = json.loads(path.read_text())
            self.assertEqual((report["status"], report["phase"]), ("incomplete", "measure:second"))
            self.assertEqual(len(report["results"]), 1)
            self.assertEqual(report["results"][0]["samples"], {"base": [1, 2, 3]})
            self.assertEqual(report["results"][0]["confirmation"], {"head": [4, 5, 6]})
            self.assertNotIn("error", report)

    def test_replacement_keeps_existing_readers_and_failed_writes_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            previous = {"status": "incomplete", "results": [self.result("first")]}
            complete = {"status": "complete", "results": [self.result("first"), self.result("second")]}
            perf.write_report(path, previous)
            with path.open() as reader:
                perf.write_report(path, complete)
                self.assertEqual(json.load(reader), previous)
            self.assertEqual(json.loads(path.read_text()), complete)
            with self.assertRaises(TypeError):
                perf.write_report(path, {"status": "error", "unserializable": object()})
            self.assertEqual(json.loads(path.read_text()), complete)


class WeeklyTests(unittest.TestCase):
    """The weekly AOT suite (#1302): every port and microbenchmark, base skips, head errors."""
    def record(self, stdout="42\n", seconds=0.5, wall=1.0):
        return {"stdout": stdout, "stderr": f"seconds {seconds}\n", "wall_s": wall, "returncode": 0}

    def test_cases_are_every_port_and_microbenchmark(self):
        cases = perf.weekly_cases(perf.ROOT)
        ports = {name: case for name, case in cases.items() if name.startswith("pyperformance/")}
        self.assertEqual(set(ports), {"pyperformance/" + name for name in bench_pyperformance.BENCHMARKS})
        for name, (path, arguments, metric) in ports.items():
            port = name.split("/", 1)[1]
            self.assertEqual(perf.ROOT / path, bench_pyperformance.port_path(port))
            self.assertEqual((arguments, metric), (bench_pyperformance.BENCHMARKS[port][0], "aot_loop_s"))
        micro = {name: case for name, case in cases.items() if name.startswith("bench/")}
        self.assertEqual(set(micro), {"bench/" + path.stem for path in (perf.ROOT / "bench").glob("*.py")})
        self.assertIn("bench/words", micro)
        self.assertIn("pyperformance/float", ports)
        self.assertTrue(all(case[1:] == ([], "aot_process_s") for case in micro.values()))
        self.assertEqual(len(cases), len(ports) + len(micro))

    def test_ten_percent_and_two_milliseconds(self):
        weekly = (perf.WEEKLY_RATIO, perf.WEEKLY_FLOOR)
        self.assertTrue(perf.compare([0.05] * 3, [0.055] * 3, *weekly)["candidate"])
        self.assertTrue(perf.compare([0.02] * 3, [0.022] * 3, *weekly)["candidate"])
        self.assertFalse(perf.compare([0.05] * 3, [0.0549] * 3, *weekly)["candidate"])
        self.assertFalse(perf.compare([0.01] * 3, [0.0119] * 3, *weekly)["candidate"])
        # (the default suite keeps its 20% and 5 ms)
        self.assertFalse(perf.compare([0.05] * 3, [0.055] * 3)["candidate"])

    def measure(self, source_exists=True, builds=None, runs=None, deadline=None):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory))
        (directory / "base").mkdir()
        (directory / "head").mkdir()
        head = directory / "checkout"
        (head / "bench").mkdir(parents=True)
        if source_exists:
            (head / "bench" / "work.py").write_text("print(42)\n")
        with mock.patch.object(perf, "execute", side_effect=builds) as executed, \
                mock.patch.object(bench_pyperformance, "execute", side_effect=runs):
            result = perf.measure_weekly("bench/work", ("bench/work.py", [], "aot_process_s"),
                                         {"base": "base-compiler", "head": "head-compiler"},
                                         {"base": {}, "head": {}}, directory, head,
                                         **({"deadline": deadline} if deadline is not None else {}))
        return result, executed

    def by_command(self, base_wall, head_wall, head_output="42\n", fail=None):
        def execute(command, env, timeout):
            if fail and fail in command[0] and "build" in command:
                raise RuntimeError(f"{fail} cannot compile it\nmore detail")
            if command[0].endswith("python3.13") or command[0] == sys.executable:
                return self.record()
            if "build" in command:
                return self.record(wall=2.0)
            side = "base" if "/base/" in command[0] else "head"
            return self.record(stdout=head_output if side == "head" else "42\n",
                               wall=(base_wall if side == "base" else head_wall).pop(0))
        return execute

    def test_unchanged_workload_is_ok_without_confirmation(self):
        result, executed = self.measure(builds=self.by_command([0.050] * 4, [0.051] * 4))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["confirmation"])
        self.assertEqual(result["samples"]["base"], [0.050] * 3)
        self.assertEqual(executed.call_count, 1 + 2 * 2 + 6)  # oracle, two builds and warmups, three pairs
        # (both builds before either warmup: a side warmed before the other's build runs colder)
        steps = [("build" if "build" in call.args[0] else "base" if "/base/" in call.args[0][0] else "head")
                 for call in executed.call_args_list[1:5]]
        self.assertEqual(steps, ["build", "build", "base", "head"])

    def test_confirmed_slowdown_warns(self):
        result, _ = self.measure(builds=self.by_command([0.050] * 7, [0.060] * 7))
        comparison = result["comparison"]["aot_process_s"]
        self.assertEqual((result["status"], comparison["status"]), ("warning", "warning"))
        self.assertEqual(len(result["confirmation"]["head"]), 3)
        self.assertAlmostEqual(comparison["ratio"], 1.2)

    def test_unconfirmed_slowdown_does_not_warn(self):
        result, _ = self.measure(builds=self.by_command([0.050] * 7, [0.060] * 4 + [0.050] * 3))
        self.assertEqual(result["status"], "unconfirmed")

    def test_missing_workload_and_failing_base_are_skipped(self):
        result, executed = self.measure(source_exists=False, builds=self.by_command([], []))
        self.assertEqual((result["status"], result["reason"]), ("skipped", "not in the head revision"))
        self.assertEqual(executed.call_count, 0)
        result, executed = self.measure(builds=self.by_command([], [0.05] * 4, fail="base-compiler"))
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "the base fails it: base-compiler cannot compile it")
        self.assertEqual(result["samples"]["head"], [0.05] * 3)
        self.assertTrue(any(call.args[0][0] == "head-compiler" for call in executed.call_args_list))

    def test_failing_head_and_wrong_head_output_are_errors(self):
        result, _ = self.measure(builds=self.by_command([0.05] * 4, [], fail="head-compiler"))
        self.assertEqual(result["status"], "error")
        self.assertIn("head-compiler cannot compile it", result["error"])
        result, _ = self.measure(builds=self.by_command([0.05] * 4, [0.05], head_output="41\n"))
        self.assertEqual(result["status"], "error")
        self.assertIn("output differs", result["error"])

    def test_base_build_failure_does_not_hide_broken_head(self):
        def execute(command, env, timeout):
            if "build" in command:
                raise RuntimeError(f"{command[0]} cannot compile it")
            return self.record()
        result, executed = self.measure(builds=execute)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "head-compiler cannot compile it")
        self.assertEqual(set(result["failures"]), {"base", "head"})
        self.assertEqual([call.args[0][0] for call in executed.call_args_list[1:]],
                         ["base-compiler", "head-compiler"])

    def test_base_warmup_failure_does_not_hide_broken_head(self):
        def execute(command, env, timeout):
            if "/base/" in command[0] or "/head/" in command[0]:
                return self.record(stdout="wrong\n")
            return self.record()
        result, _ = self.measure(builds=execute)
        self.assertEqual(result["status"], "error")
        self.assertEqual({side: failure["phase"] for side, failure in result["failures"].items()},
                         {"base": "warmup", "head": "warmup"})

    def test_timed_and_confirmation_failures_keep_samples_and_check_other_side(self):
        for side in ("base", "head"):
            for phase, attempt in (("sample:1", 2), ("confirmation:1", 5)):
                for error in (RuntimeError("timeout after 300s"), ValueError("wrong output"), OSError("missing executable")):
                    with self.subTest(side=side, phase=phase, error=error):
                        calls = {"base": 0, "head": 0}
                        normal = self.by_command([0.05] * 7, [0.06] * 7)

                        def execute(command, env, timeout, *, calls=calls, side=side, attempt=attempt,
                                    error=error, normal=normal):
                            for which in calls:
                                if f"/{which}/" in command[0]:
                                    calls[which] += 1
                                    if which == side and calls[which] == attempt:
                                        raise error
                            return normal(command, env, timeout)

                        result, _ = self.measure(builds=execute)
                        self.assertEqual(result["status"], "skipped" if side == "base" else "error")
                        self.assertEqual(result["failures"][side], {"phase": phase, "error": str(error)})
                        other = "head" if side == "base" else "base"
                        batch = result["confirmation"] if attempt == 5 else result["samples"]
                        self.assertEqual(len(batch[other]), 3)
                        self.assertEqual(batch[side], [])
                        if attempt == 5:
                            self.assertEqual([len(v) for v in result["samples"].values()], [3, 3])

    def test_deadline_caps_oracle_build_warmup_samples_and_confirmation(self):
        for deadline in (0.5, 1.5, 3.5, 5.5, 12.5):
            with self.subTest(deadline=deadline):
                clock = [0.0]
                timeouts = []

                def execute(command, env, timeout, *, deadline=deadline, clock=clock, timeouts=timeouts):
                    self.assertLessEqual(timeout, deadline - clock[0])
                    timeouts.append(timeout)
                    if timeout < 1:
                        clock[0] += timeout
                        raise RuntimeError(f"timeout after {timeout}s: command")
                    clock[0] += 1
                    return self.record(wall=0.06 if "/head/" in command[0] else 0.05)

                with mock.patch.object(perf.time, "monotonic", side_effect=lambda clock=clock: clock[0]):
                    result, _ = self.measure(builds=execute, deadline=deadline)
                self.assertEqual((result["status"], result["reason"]), ("skipped", "out of the time budget"))
                self.assertTrue(result["budget_exhausted"])
                self.assertEqual(result["failures"], {})
                self.assertEqual(clock[0], deadline)
                self.assertEqual(timeouts[-1], 0.5)
                if deadline == 12.5:
                    self.assertEqual([len(v) for v in result["samples"].values()], [3, 3])
                    self.assertEqual([len(v) for v in result["confirmation"].values()], [0, 1])

    def test_timed_port_receives_the_remaining_budget(self):
        with mock.patch.object(perf.time, "monotonic", return_value=9.75), \
                mock.patch.object(bench_pyperformance, "execute", return_value=self.record()) as execute:
            perf.aot_sample("port", [], {}, "42\n", "aot_loop_s", deadline=10)
        self.assertEqual(execute.call_args.args[2], 0.25)

    def test_expired_deadline_does_not_start_a_command(self):
        with mock.patch.object(perf.time, "monotonic", return_value=10), \
                mock.patch.object(perf, "execute") as execute, self.assertRaises(perf.BudgetExhausted):
            perf.aot_sample("port", [], {}, "42\n", "aot_process_s", deadline=10)
        execute.assert_not_called()

    def test_bootstrap_deadline_keeps_report_and_marks_unmeasured_workloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            clock = [0.0]

            def execute(command, env, timeout):
                if "build" in command:
                    self.assertEqual(timeout, 1.0)
                    clock[0] += timeout
                    raise RuntimeError(f"timeout after {timeout}s: compiler")
                clock[0] += 1
                return self.record(stdout="revision\n")

            with mock.patch.object(sys, "argv", ["perf_smoke.py", "--suite", "weekly", "--budget", "2",
                                                 "--only", "bench/fib,bench/words",
                                                 "--base", directory, "--json", str(path)]), \
                    mock.patch.object(perf.time, "monotonic", side_effect=lambda: clock[0]), \
                    mock.patch.object(perf, "execute", side_effect=execute), \
                    mock.patch.object(perf, "measure_weekly") as measured, \
                    mock.patch.object(perf.os, "sched_getaffinity", return_value={0, 1}), \
                    mock.patch.object(perf.os, "sched_setaffinity") as affinity, \
                    contextlib.redirect_stdout(io.StringIO()):
                perf.main()
            report = json.loads(path.read_text())
            self.assertEqual((report["status"], report["phase"]), ("incomplete", "bootstrap:base"))
            self.assertTrue(report["budget_exhausted"])
            self.assertEqual([result["name"] for result in report["results"]], ["bench/fib", "bench/words"])
            self.assertTrue(all(result["budget_exhausted"] for result in report["results"]))
            measured.assert_not_called()
            self.assertEqual(affinity.call_args_list[-1], mock.call(0, [0, 1]))

    def test_port_metric_is_the_timed_part(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory))
        exe = str(directory / "work")
        with mock.patch.object(bench_pyperformance, "execute", return_value=self.record(seconds=0.25, wall=3.0)):
            self.assertEqual(perf.aot_sample(exe, [], {}, "42\n", "aot_loop_s"), 0.25)
        with mock.patch.object(perf, "execute", return_value=self.record(seconds=0.25, wall=3.0)):
            self.assertEqual(perf.aot_sample(exe, [], {}, "42\n", "aot_process_s"), 3.0)
            with self.assertRaisesRegex(ValueError, "output differs"):
                perf.aot_sample(exe, [], {}, "41\n", "aot_process_s")

    def test_summary_lists_milliseconds_skips_and_errors(self):
        compared = perf.compare([0.050] * 3, [0.060] * 3, perf.WEEKLY_RATIO, perf.WEEKLY_FLOOR)
        compared.update(status="warning")
        report = {"revisions": {"base": "b", "head": "h"}, "results": [
            {"name": "bench/words", "status": "warning", "comparison": {"aot_process_s": compared}},
            {"name": "pyperformance/go", "status": "skipped", "reason": "the base fails it: x"},
            {"name": "bench/fib", "status": "error", "error": "exit 1: fib\ndetail"}]}
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            text = perf.weekly_summary(report)
        self.assertIn("| bench/words | aot_process_s | 50.00 ms | 60.00 ms | +20.0% | warning |", text)
        self.assertIn("- pyperformance/go: skipped, the base fails it: x", text)
        self.assertIn("- bench/fib: error, exit 1: fib", text)
        self.assertIn("::warning::bench/words aot_process_s: confirmed >=10% slowdown", printed.getvalue())

    def test_head_errors_fail_the_run_after_the_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            record = {"stdout": "revision\n", "stderr": "", "wall_s": 1.0, "returncode": 0}
            results = [{"name": "bench/b", "status": "error", "error": "exit 1"},
                       {"name": "bench/a", "status": "ok", "comparison": {}}]
            env = {key: value for key, value in os.environ.items() if key != "GITHUB_STEP_SUMMARY"}
            with mock.patch.object(sys, "argv", ["perf_smoke.py", "--suite", "weekly", "--only", "bench/fib,bench/words",
                                                 "--base", str(path.parent), "--json", str(path)]), \
                    mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(perf, "execute", return_value=record), \
                    mock.patch.object(perf, "measure_weekly", side_effect=results) as measured, \
                    mock.patch.object(perf.os, "sched_getaffinity", return_value={0, 1}), \
                    mock.patch.object(perf.os, "sched_setaffinity"), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    self.assertRaisesRegex(RuntimeError, "the head revision fails 1 workloads: bench/b"):
                perf.main()
            self.assertEqual([call.args[0] for call in measured.call_args_list], ["bench/fib", "bench/words"])
            report = json.loads(path.read_text())
            self.assertEqual((report["suite"], report["status"]), ("weekly", "error"))
            self.assertEqual(report["thresholds"], {"ratio": perf.WEEKLY_RATIO, "floor_s": perf.WEEKLY_FLOOR})
            self.assertEqual(report["results"], results)

    def test_budget_skips_the_remaining_workloads_and_options_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            record = {"stdout": "revision\n", "stderr": "", "wall_s": 1.0, "returncode": 0}
            env = {key: value for key, value in os.environ.items() if key != "GITHUB_STEP_SUMMARY"}
            clock = [0.0]

            def measure(*args):
                clock[0] = 5.0
                return {"name": "bench/fib", "status": "ok", "comparison": {}}

            with mock.patch.object(sys, "argv", ["perf_smoke.py", "--suite", "weekly", "--budget", "2",
                                                 "--only", "bench/fib,bench/words",
                                                 "--base", str(path.parent), "--json", str(path)]), \
                    mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(perf.time, "monotonic", side_effect=lambda: clock[0]), \
                    mock.patch.object(perf, "execute", return_value=record), \
                    mock.patch.object(perf, "measure_weekly", side_effect=measure), \
                    mock.patch.object(perf.os, "sched_getaffinity", return_value={0, 1}), \
                    mock.patch.object(perf.os, "sched_setaffinity"), \
                    contextlib.redirect_stdout(io.StringIO()):
                perf.main()
            report = json.loads(path.read_text())
            self.assertEqual(report["status"], "incomplete")
            self.assertEqual(report["results"][1], {"name": "bench/words", "status": "skipped",
                                                    "reason": "out of the time budget", "budget_exhausted": True})
        for argv in (["--budget", "5"], ["--head", "/"], ["--suite", "weekly", "--only", "bench/none"],
                     ["--suite", "weekly", "--budget", "-1"], ["--suite", "weekly", "--budget", "nan"],
                     ["--suite", "weekly", "--budget", "inf"]):
            with self.subTest(argv=argv), mock.patch.object(sys, "argv", ["perf_smoke.py", "--base", ".", *argv]), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                perf.main()


if __name__ == "__main__":
    unittest.main()
