"""Controls for installed-wheel API evidence and correctness-before-timing."""
import copy
from contextlib import redirect_stdout
import io
import json
from importlib.machinery import ExtensionFileLoader, SourceFileLoader
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import json_repair_api_bench as bench


class ApiEvidenceTests(unittest.TestCase):
    def test_tagged_witnesses_reject_type_order_and_codepoint_loss(self):
        pairs = [(True, 1), (1, 1.0), (0.0, -0.0), ([1], (1,)),
                 ({"a": 1, "b": 2}, {"b": 2, "a": 1}), ("\ud83d\ude00", "\U0001f600")]
        for left, right in pairs:
            with self.subTest(left=repr(left), right=repr(right)), self.assertRaisesRegex(ValueError, "parity"):
                bench.compare_witnesses({"case": bench.tagged(left)}, {"case": bench.tagged(right)}, "control")
        for value in (True, 1, -0.0, "\ud83d\ude00", {"x": [None, 2, 2.0]}):
            original = {"case": bench.tagged(value)}
            bench.compare_witnesses(original, json.loads(json.dumps(original)), "round trip")

    def test_mix_covers_all_shapes_at_explicit_proportions(self):
        sources = bench.workloads()
        self.assertEqual(len(sources["valid"]), len(sources["malformed"]))
        self.assertEqual(len(sources["mixed"]), len(sources["valid"]) * 5)
        for source in sources["valid"]:
            json.loads(source)
            self.assertEqual(sources["mixed"].count(source), 4)
        for source in sources["malformed"]:
            with self.assertRaises(ValueError):
                json.loads(source)
            self.assertEqual(sources["mixed"].count(source), 1)

    def test_mismatch_stops_before_performance_children(self):
        args = SimpleNamespace(upstream=Path("."), adapted=Path("."), timeout=10)
        calls = []

        def child(command, timeout):
            calls.append(command)
            backend = command[command.index("--backend") + 1]
            return {"witnesses": {"case": bench.tagged(1 if backend != "installed" else True)}}

        with mock.patch.object(bench, "check_upstream", return_value={}), \
                mock.patch.object(bench, "source_identity", return_value={}), \
                mock.patch.object(bench, "run_child", side_effect=child), \
                self.assertRaisesRegex(ValueError, "installed"):
            bench.campaign(args)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(command[command.index("--phase") + 1] == "parity" for command in calls))
        self.assertTrue(all(command[1] == "-I" for command in calls))

    def test_pristine_source_pin_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src/json_repair/__init__.py"
            source.parent.mkdir(parents=True)
            source.write_text("fixture\n")
            manifest = root / "tests/upstream/json_repair/manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"tag": "v0.64.1", "commit": "pinned",
                                            "source_sha256": {"src/json_repair/__init__.py": bench.digest(source)}}))
            with mock.patch.object(bench, "ROOT", root):
                self.assertEqual(bench.check_upstream(root)["version"], "v0.64.1")
                shadow = root / "src/json.py"
                shadow.write_text("# unexpected import shadow\n")
                with self.assertRaisesRegex(ValueError, "importable sources differ"):
                    bench.check_upstream(root)
                shadow.unlink()
                source.write_text("changed\n")
                with self.assertRaisesRegex(ValueError, "not pristine"):
                    bench.check_upstream(root)

    def test_python_standin_is_not_an_installed_native_backend(self):
        fake = SimpleNamespace(_native=SimpleNamespace(__spec__=SimpleNamespace(
            loader=SourceFileLoader("_native", "fake.py"))))
        with mock.patch.object(bench.importlib, "import_module", return_value=fake), \
                self.assertRaisesRegex(ValueError, "native extension"):
            bench.load_backend("installed", "")

    def test_import_path_must_match_selected_tree(self):
        fake = SimpleNamespace(__file__="/different/json_repair/__init__.py")
        original = sys.path[:]
        try:
            with mock.patch.object(bench.importlib, "import_module", return_value=fake), \
                    self.assertRaisesRegex(ValueError, "outside the selected source"):
                bench.load_backend("adapted", "/selected")
        finally:
            sys.path[:] = original

    def test_installed_receipt_requires_distribution_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper, native = root / "__init__.py", root / "_native.abi3.so"
            wrapper.write_text("wrapper")
            native.write_bytes(b"fixture")
            fake = SimpleNamespace(__file__=str(wrapper), _native=SimpleNamespace(__file__=str(native)))
            distribution = SimpleNamespace(version="0.1", files=[wrapper, native],
                                           locate_file=lambda path: path, read_text=lambda name: "Tag: cp312-abi3-linux_x86_64")
            with mock.patch("importlib.metadata.distribution", return_value=distribution):
                receipt = bench.installed_identity(fake)
                self.assertEqual(receipt["sha256"][str(native)], bench.digest(native))
                distribution.files = [wrapper]
                with self.assertRaisesRegex(ValueError, "installed wheel distribution"):
                    bench.installed_identity(fake)
            fake._native.__spec__ = SimpleNamespace(loader=ExtensionFileLoader("_native", str(native)))
            with mock.patch.object(bench.importlib, "import_module", return_value=fake):
                self.assertIs(bench.load_backend("installed", ""), fake)

    def test_expected_timing_witness_preserves_mix_order(self):
        sources = bench.workloads()
        reference = {f"{name}/{index}/objects/False": {"value": bench.tagged([name, index])}
                     for name in ("valid", "malformed") for index in range(len(sources[name]))}
        expected = [[name, index] for index in range(8) for name in ["valid"] * 4 + ["malformed"]]
        self.assertEqual(bench.expected_witness(reference, "objects", "mixed"), bench.tagged(expected))
        reference["malformed/0/objects/False"] = {"error": "ValueError", "message": "bad"}
        with self.assertRaisesRegex(ValueError, "timing workload raised"):
            bench.expected_witness(reference, "objects", "mixed")

    def test_invalid_batch_results_fail(self):
        good = {"seconds": [0.1, 0.2], "warmup_seconds": [0.3]}
        bench.validate_samples(good, 2, 1)
        for values in ([0.1], [0.1, 0.2, 0.3], [float("nan"), 0.2], [float("inf"), 0.2],
                       [-0.1, 0.2], [True, 0.2], ["0.1", 0.2]):
            changed = copy.deepcopy(good)
            changed["seconds"] = values
            with self.subTest(values=values), self.assertRaises(ValueError):
                bench.validate_samples(changed, 2, 1)
        with self.assertRaises(ValueError):
            bench.validate_samples({"seconds": [0.1, 0.2]}, 2, 1)

    def test_repeated_call_checks_detect_corruption(self):
        expected = [{"x": 1}]
        for values in (({"x": 1, "y": 2}, {"x": 1}), ({"x": 1}, {"x": True})):
            with self.subTest(values=values):
                module = SimpleNamespace(loads=mock.Mock(side_effect=values))
                with self.assertRaisesRegex(ValueError, "changed"):
                    bench.call_batch(module, "objects", ["input"], 1, 2, expected)
                self.assertEqual(module.loads.call_count, 2)

    def test_isolated_worker_counts_real_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "ports/json_repair"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("def loads(source, **flags):\n    return {'source': source}\n")
            command = [sys.executable, "-I", str(Path(bench.__file__).resolve()), "--worker",
                       "--backend", "adapted", "--root", str(root), "--phase", "steady", "--api", "objects",
                       "--rounds", "2", "--batches", "1", "--warmups", "0", "--group-size", "32",
                       "--min-sample-seconds", "0"]
            result = bench.run_child(command, 10)
            bench.validate_samples(result, 1, 0)
            self.assertEqual(result["requests_per_sample"], 2 * len(bench.workloads()["mixed"]))
            self.assertGreater(result["process_wall_seconds"], 0)
            command[command.index("--phase") + 1] = "memory"
            memory = bench.run_child(command, 10)["memory_samples"]
            self.assertEqual([row["requests_after_warmup"] for row in memory], [0, 80])
            for row in memory:
                self.assertIn("current_rss_bytes", row)
                self.assertIn("process_peak_rss_bytes", row)
                self.assertIn("current_rss_source", row)
                self.assertIn("process_peak_rss_source", row)

    def test_failed_child_does_not_produce_valid_evidence(self):
        with self.assertRaisesRegex(RuntimeError, "child failed"):
            bench.run_child([sys.executable, "-c", "raise SystemExit(3)"], 10)
        with self.assertRaises(json.JSONDecodeError):
            bench.run_child([sys.executable, "-c", "print('not json')"], 10)
        with self.assertRaises(subprocess.TimeoutExpired):
            bench.run_child([sys.executable, "-c", "import time; time.sleep(1)"], 0.01)


class MemoryEvidenceTests(unittest.TestCase):
    def test_linux_counters_ignore_inherited_rusage_and_statm(self):
        usage = mock.Mock(return_value=SimpleNamespace(ru_maxrss=900_000))
        resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=usage)

        def read_status(path):
            self.assertEqual(str(path), "/proc/self/status")
            return "Name:\tworker\nVmHWM:\t12340 kB\nVmRSS:\t11836 kB\n"

        with mock.patch.object(bench.sys, "platform", "linux"), \
                mock.patch.object(Path, "read_text", read_status), \
                mock.patch.dict(sys.modules, {"resource": resource}):
            snapshot = bench.memory_snapshot()
        self.assertEqual(snapshot["current_rss_bytes"], 11836 * 1024)
        self.assertEqual(snapshot["process_peak_rss_bytes"], 12340 * 1024)
        self.assertEqual(snapshot["current_rss_source"], "/proc/self/status:VmRSS")
        self.assertEqual(snapshot["process_peak_rss_source"], "/proc/self/status:VmHWM")
        self.assertIn("since exec", snapshot["process_peak_rss_scope"])
        usage.assert_not_called()

    def test_missing_or_invalid_linux_counters_do_not_fall_back(self):
        usage = mock.Mock(return_value=SimpleNamespace(ru_maxrss=900_000))
        resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=usage)
        for status in ("VmRSS: 12 kB\n", "VmHWM: 12 kB\n",
                       "VmHWM: 12 kB\nVmRSS: 11 MB\n", "VmHWM: 12 kB\nVmRSS: -1 kB\n",
                       "VmHWM: 12 kB\nVmRSS: 11\n", "VmHWM: 12 kB\nVmRSS: 11 kB\nVmRSS: 10 kB\n"):
            with self.subTest(status=status), mock.patch.object(bench.sys, "platform", "linux"), \
                    mock.patch.object(Path, "read_text", return_value=status), \
                    mock.patch.dict(sys.modules, {"resource": resource}), self.assertRaises(ValueError):
                bench.memory_snapshot()
        with mock.patch.object(bench.sys, "platform", "linux"), \
                mock.patch.object(Path, "read_text", side_effect=FileNotFoundError("no proc status")), \
                mock.patch.dict(sys.modules, {"resource": resource}), self.assertRaises(FileNotFoundError):
            bench.memory_snapshot()
        usage.assert_not_called()

    def test_non_linux_fallback_identifies_its_scope_and_units(self):
        usage = mock.Mock(return_value=SimpleNamespace(ru_maxrss=12340))
        resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=usage)
        for platform, multiplier in (("darwin", 1), ("freebsd", 1024)):
            with self.subTest(platform=platform), mock.patch.object(bench.sys, "platform", platform), \
                    mock.patch.object(Path, "read_text", side_effect=AssertionError("unexpected Linux counter read")), \
                    mock.patch.dict(sys.modules, {"resource": resource}):
                snapshot = bench.memory_snapshot()
            self.assertIsNone(snapshot["current_rss_bytes"])
            self.assertIsNone(snapshot["current_rss_source"])
            self.assertEqual(snapshot["process_peak_rss_bytes"], 12340 * multiplier)
            self.assertIn("non-Linux fallback", snapshot["process_peak_rss_source"])
            self.assertIn("inherited pre-exec", snapshot["process_peak_rss_scope"])


class CalibrationTests(unittest.TestCase):
    def test_worker_uses_calibrated_denominator_and_excludes_probes(self):
        args = SimpleNamespace(backend="adapted", root="unused", phase="steady", api="objects",
                               workload="valid", group_size=1, rounds=2, warmups=1, batches=2,
                               min_sample_seconds=0.2)
        module = SimpleNamespace(loads=lambda source, **flags: json.loads(source))
        output = io.StringIO()
        with mock.patch.object(bench, "load_backend", return_value=module), \
                mock.patch.object(bench, "memory_snapshot", return_value={}), \
                mock.patch.object(bench, "call_batch", side_effect=[0.01, 0.25, 0.3, 0.22, 0.21]) as batch, \
                redirect_stdout(output):
            bench.worker(args)
        result = json.loads(output.getvalue())
        self.assertGreater(result["rounds"], args.rounds)
        self.assertEqual(result["requests_per_sample"], result["rounds"] * len(bench.workloads()["valid"]))
        self.assertEqual(result["warmup_seconds"], [0.3])
        self.assertEqual(result["seconds"], [0.22, 0.21])
        probes = result["calibration"]["samples"]
        self.assertEqual([probe["seconds"] for probe in probes], [0.01, 0.25])
        self.assertEqual(probes[-1]["rounds"], result["rounds"])
        self.assertEqual(probes[-1]["requests"], result["requests_per_sample"])
        self.assertEqual(result["calibration"]["status"], "target_reached")
        self.assertEqual([call.args[4] for call in batch.call_args_list[2:]], [result["rounds"]] * 3)

    def test_zero_target_disables_calibration(self):
        with mock.patch.object(bench, "call_batch", side_effect=AssertionError("unexpected calibration")):
            rounds, evidence = bench.calibrate(None, "objects", ["{}"], 1, 7, [{}], 0)
        self.assertEqual(rounds, 7)
        self.assertEqual(evidence["status"], "disabled")
        self.assertEqual(evidence["samples"], [])

    def test_calibration_has_round_and_probe_limits(self):
        for limit, duration, expected_status in ((10, 0, "round_limit"), (1_000_000, 0.1, "step_limit")):
            with self.subTest(limit=limit), mock.patch.object(bench, "CALIBRATION_ROUNDS", limit), \
                    mock.patch.object(bench, "CALIBRATION_STEPS", 3), \
                    mock.patch.object(bench, "call_batch", return_value=duration) as batch:
                rounds, evidence = bench.calibrate(None, "objects", ["{}"], 1, 2, [{}], 1)
            self.assertLessEqual(rounds, limit)
            self.assertLessEqual(batch.call_count, 3)
            self.assertEqual(evidence["status"], expected_status)
            self.assertEqual(evidence["samples"][-1]["rounds"], rounds)

    def test_invalid_targets_fail_before_calibration_or_backend_loading(self):
        for target in (-1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(target=target), mock.patch.object(bench, "call_batch") as batch:
                with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                    bench.calibrate(None, "objects", ["{}"], 1, 2, [{}], target)
                batch.assert_not_called()
            result = subprocess.run([sys.executable, str(Path(bench.__file__).resolve()),
                                     f"--min-sample-seconds={target}"], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("min-sample-seconds must be finite and nonnegative", result.stderr)

    def test_invalid_calibration_timings_are_rejected(self):
        for duration in (-0.1, float("nan"), float("inf"), True):
            with self.subTest(duration=duration), mock.patch.object(bench, "call_batch", return_value=duration):
                with self.assertRaisesRegex(ValueError, "invalid calibration timing"):
                    bench.calibrate(None, "objects", ["{}"], 1, 2, [{}], 0.2)

    def test_memory_request_counts_are_not_calibrated(self):
        args = SimpleNamespace(backend="adapted", root="unused", phase="memory", api="objects",
                               workload="valid", group_size=1, rounds=2, batches=2, min_sample_seconds=0.2)
        module = SimpleNamespace(loads=lambda source, **flags: json.loads(source))
        output = io.StringIO()
        with mock.patch.object(bench, "load_backend", return_value=module), \
                mock.patch.object(bench, "memory_snapshot", return_value={}), \
                mock.patch.object(bench, "calibrate", side_effect=AssertionError("memory must not calibrate")), \
                mock.patch.object(bench, "call_batch", return_value=0.01) as batch, redirect_stdout(output):
            bench.worker(args)
        result = json.loads(output.getvalue())
        per_block = args.rounds * len(bench.workloads()["valid"])
        self.assertEqual([row["requests_after_warmup"] for row in result["memory_samples"]], [0, per_block, 2 * per_block])
        self.assertEqual([call.args[4] for call in batch.call_args_list], [args.rounds] * 3)


if __name__ == "__main__":
    unittest.main()
