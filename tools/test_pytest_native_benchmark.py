"""Keep benchmark correctness and timing boundaries independently checkable."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pytest_native as runner

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pytest_native_bench", ROOT / "bench/pytest_native/bench.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class BenchmarkControls(unittest.TestCase):
    def test_baseline_has_no_reporting_plugin(self):
        command = bench.pytest_command(sys.executable, Path("test_suite.py"), Path("empty.ini"))
        self.assertNotIn("_pyn_oracle", command)
        self.assertEqual([command[index + 1] for index, part in enumerate(command) if part == "-p"],
                         ["no:cacheprovider"])
        self.assertIn("-s", command)

    def test_environment_rejects_assertion_and_plugin_contamination(self):
        with patch.dict(os.environ, {"PYTHONOPTIMIZE": "1", "PYTEST_ADDOPTS": "-x",
                                    "PYTEST_PLUGINS": "fake", "PYSTACHY_GC_STRESS": "1",
                                    "PYTHONTRACEMALLOC": "25", "PYTHONMALLOC": "debug",
                                    "PYTHONPROFILEIMPORTTIME": "1", "PYTHONWARNINGS": "error",
                                    "PYSTACHY_LLVM": "/toolchain", "LD_LIBRARY_PATH": "/toolchain/lib"}):
            env = bench.environment(Path("input"), Path("cache"))
        for name in ("PYTHONOPTIMIZE", "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYSTACHY_GC_STRESS",
                     "PYTHONTRACEMALLOC", "PYTHONMALLOC", "PYTHONPROFILEIMPORTTIME", "PYTHONWARNINGS"):
            self.assertNotIn(name, env)
        self.assertEqual(env["PYSTACHY_PROGRAM_CACHE"], "0")
        self.assertEqual(env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"], "1")
        self.assertEqual(env["PYSTACHY_LLVM"], "/toolchain")
        self.assertEqual(env["LD_LIBRARY_PATH"], "/toolchain/lib")

    def test_missing_reordered_or_wrong_checksum_is_not_a_sample(self):
        expected = [("0", "11"), ("1", "12")]
        bench.validate_checksums("BENCH 0 11\n.BENCH 1 12\n", expected)
        for actual in ("BENCH 0 11", "BENCH 0 11\nBENCH 1 13", "BENCH 1 12\nBENCH 0 11",
                       "BENCH 0 11\nBENCH 0 11\nBENCH 1 12"):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                bench.validate_checksums(actual, expected)

    def test_pytest_skip_or_partial_inventory_cannot_improve_timing(self):
        valid = {"returncode": 0, "stdout": "BENCH 0 11\n1 passed in 0.10s\n", "stderr": ""}
        bench.validate_pytest(valid, [("0", "11")])
        with self.assertRaises(ValueError):
            bench.validate_pytest(dict(valid, stdout="BENCH 0 11\n1 passed, 1 skipped in 0.10s"),
                                  [("0", "11")])
        with self.assertRaises(ValueError):
            bench.validate_pytest(valid, [("0", "11"), ("1", "12")])

    def test_failed_process_cannot_be_a_sample(self):
        with self.assertRaises(ValueError):
            bench.checked({"command": ["false"], "returncode": 1, "stdout": "", "stderr": "failure"})

    def test_distributions_and_break_even_include_upfront_cost(self):
        stats = bench.distribution([{"seconds": value, "peak_rss_bytes": 100} for value in (2, 1, 3)])
        self.assertEqual(stats["median_seconds"], 2)
        self.assertEqual(stats["count"], 3)
        self.assertEqual(bench.break_even(10, 2, 1), 10)
        self.assertIsNone(bench.break_even(10, 1, 2))

    def test_wait4_records_exact_process_completion_and_nonzero_status(self):
        record = bench.measured([sys.executable, "-c", "print('sample'); raise SystemExit(3)"],
                                os.environ.copy(), 10)
        self.assertEqual(record["returncode"], 3)
        self.assertEqual(record["stdout"], "sample\n")
        self.assertGreater(record["peak_rss_bytes"], 0)
        self.assertGreater(record["seconds"], 0)

    def test_work_dir_and_sample_bounds_are_enforced(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                bench.main(["--work-dir", temp, "--json", temp + "/data.json",
                            "--markdown", temp + "/data.md", "--samples", "2"])

    def test_each_workload_matches_real_pytest_before_native_timing(self):
        for name in bench.SUITES:
            with self.subTest(suite=name), tempfile.TemporaryDirectory(prefix="pytest-bench-") as temp:
                directory = Path(temp)
                source = bench.HERE / ("test_" + name + ".py")
                input_path = bench.HERE / "inputs" / (name + (".txt" if name == "fixtures" else ".tsv"))
                env = bench.environment(input_path, directory / "cache")
                checksums = bench.expected_checksums(name, input_path)
                with patch.dict(os.environ, env, clear=True):
                    results = runner.run_suite([source], ROOT, directory / "generated", "python", [],
                                               sys.executable, 30)
                    reference = runner.oracle([source], ROOT, directory / "oracle", sys.executable, 30)
                self.assertEqual(runner.compare(results, reference), [])
                self.assertTrue(all(result.state == "passed" for result in results))
                self.assertEqual(len(results[0].cases), len(checksums))
                bench.validate_checksums(results[0].stdout, checksums)
                config = directory / "empty.ini"
                config.write_text("[pytest]\n")
                plain = bench.measured(bench.pytest_command(sys.executable, source, config), env, 30)
                bench.validate_pytest(plain, checksums)

    def test_edit_control_changes_the_executed_checksum(self):
        with tempfile.TemporaryDirectory(prefix="pytest-bench-edit-") as temp:
            directory = Path(temp)
            source = directory / "test_fixtures.py"
            original = (bench.HERE / source.name).read_text()
            source.write_text(original.replace("REVISION = 0", "REVISION = 1"))
            inputs = bench.HERE / "inputs/fixtures.txt"
            with patch.dict(os.environ, bench.environment(inputs, directory / "cache"), clear=True):
                results = runner.run_suite([source], directory, directory / "work", "python", [],
                                           sys.executable, 30)
            self.assertEqual(results[0].state, "passed")
            bench.validate_checksums(results[0].stdout, bench.expected_checksums("fixtures", inputs, 1))
            with self.assertRaises(ValueError):
                bench.validate_checksums(results[0].stdout, bench.expected_checksums("fixtures", inputs))

    def test_preparation_is_nonexecuting_and_preserves_cases(self):
        with tempfile.TemporaryDirectory(prefix="pytest-bench-prepare-") as temp:
            prepared = Path(temp) / "prepared"
            info = bench.prepare(bench.HERE / "test_fixtures.py", prepared)
            self.assertEqual(len(info["cases"]), 16)
            self.assertEqual(info, json.loads((prepared / "manifest.json").read_text()))
            self.assertEqual(info["generated_sha256"], bench.digest(Path(info["source"])))
            self.assertFalse((prepared / "events.jsonl").exists())
            with self.assertRaises(FileExistsError):
                bench.prepare(bench.HERE / "test_fixtures.py", prepared)


if __name__ == "__main__":
    unittest.main()
