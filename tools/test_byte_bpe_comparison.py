"""Reject misleading comparison evidence and accidental interpreted fallbacks."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "examples/byte_bpe/compare"


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = SimpleNamespace(**runpy.run_path(str(HERE / "run.py")))

    def test_rejects_bad_timing_rows(self):
        valid = "first_train 2\nsecond_train 1.5\ntrain 1\nencode 0.5\ndecode 0.1\n"
        self.assertEqual(set(self.runner.parse_times(valid)), set(self.runner.TIMINGS))
        for bad in ("", valid + "decode 1\n", valid.replace("second_train", "first_train"),
                    valid.replace("0.5", "nan"), valid.replace("0.5", "inf"),
                    valid.replace("0.5", "0"), valid.replace("0.5", "-1")):
            with self.subTest(stderr=bad), self.assertRaises(ValueError):
                self.runner.parse_times(bad)

    def test_complete_output_and_per_operation_normalization(self):
        record = {"stdout": "ranks\ntokens\nbytes\ntext\n",
                  "stderr": "first_train 2\nsecond_train 1.5\ntrain 1\nencode 0.5\ndecode 0.1\n"}
        with self.assertRaisesRegex(ValueError, "differs from original"):
            self.runner.checked_sample(dict(record), "wrong", 50, 200)
        checked = self.runner.checked_sample(record, record["stdout"], 50, 200)
        self.assertEqual(checked["encode_seconds"], .01)
        self.assertEqual(checked["decode_seconds"], .0005)
        self.assertNotIn("stdout", checked)

    def test_adapters_reproduce_measured_source_hashes(self):
        original = (HERE.parent / "upstream/bpe_tokeniser.py").read_text()
        expected = {
            "cython_original": "c7255345499e118181785370b0996e8cc1056491b9678b3fbeb02421e3f9b2df",
            "cython_scalar": "5da6c2151bb957e5477c14d430c816ff293bd3e8b64e4ae8720a1248da6be0c4",
            "mypyc_original": "5c6daefb08269934beab79bbd62dc81842e26e82ce536e74a6096a216d730764",
        }
        for mode, digest in expected.items():
            with self.subTest(mode=mode):
                result = self.runner.adapter(original, mode)
                self.assertEqual(hashlib.sha256(result.encode()).hexdigest(), digest)
        for source in ("", original.replace("stats = collections.Counter()", "stats = {}")):
            with self.assertRaisesRegex(ValueError, "exactly one"):
                self.runner.adapter(source, "mypyc_original")

    def test_extension_launcher_rejects_python_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "bpe_tokeniser.py").write_text("# A .py fallback must never count as compiled.\n")
            driver = directory / "driver.py"
            driver.write_text("raise AssertionError('driver must not run')\n")
            result = subprocess.run([sys.executable, str(HERE / "launch.py"), str(directory), str(driver)],
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("expected the freshly built native extension", result.stderr)
            self.assertNotIn("AssertionError", result.stderr)

    def test_known_pypy_error_texts_only(self):
        expected = 'exhausted "" 257 max() iterable argument is empty\n'
        for text in ("max() arg is an empty sequence", "arg is an empty sequence"):
            self.assertEqual(self.runner.fixture_output(expected.replace("max() iterable argument is empty", text)), expected)
        self.assertEqual(self.runner.fixture_output("unexpected failure"), "unexpected failure")

    def test_bad_arguments_fail_before_execution(self):
        for arguments in (["--modes", "cpython_original,cpython_original"], ["--modes", "unknown"],
                          ["--processes", "0"], ["--encode-loops", "0"], ["--timeout", "nan"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.runner.main(["--output", "/unused.json", *arguments])

    def test_failed_input_check_replaces_old_success(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            output.write_text('{"status":"passed"}')
            with mock.patch.object(self.runner.benchmark, "CORPUS_SHA256", "wrong"):
                with self.assertRaisesRegex(ValueError, "corpus SHA-256 mismatch"):
                    self.runner.main(["--python", sys.executable, "--modes", "cpython_original", "--output", str(output)])
            self.assertEqual(json.loads(output.read_text())["status"], "failed")

    def test_assertions_and_noninteractive_execution_are_preserved(self):
        with mock.patch.dict(os.environ, PYTHONOPTIMIZE="2", PYTHONINSPECT="1", PYSTACHY_GC_MIN="1", PYPYLOG="jit:log", clear=True):
            env = self.runner.clean_env()
        for name in ("PYTHONOPTIMIZE", "PYTHONINSPECT", "PYSTACHY_GC_MIN", "PYPYLOG"):
            self.assertFalse(name in env, name)
        self.assertEqual(env["PYTHONHASHSEED"], "0")

    def test_build_timeout_kills_compiler_process_group(self):
        process = mock.Mock(pid=123)
        process.communicate.side_effect = [subprocess.TimeoutExpired(["compiler"], 1), ("", "")]
        with mock.patch.object(self.runner.subprocess, "Popen", return_value=process) as popen, \
                mock.patch.object(self.runner.os, "killpg") as killpg:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.runner.build(["compiler"], {}, ROOT, 1)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        killpg.assert_called_once_with(123, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)

    def test_python_cannot_be_mislabeled_as_pypy(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            with self.assertRaisesRegex(ValueError, "pypy mode requires pypy"):
                self.runner.main(["--python", sys.executable, "--pypy", sys.executable,
                                  "--modes", "pypy_original", "--smoke", "--output", str(output)])
            self.assertEqual(json.loads(output.read_text())["status"], "failed")


class RecordedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = HERE.parent / "results/runtime-comparison-2026-11-07"
        cls.audit = SimpleNamespace(**runpy.run_path(str(cls.directory / "verify.py")))

    def test_archived_evidence_is_consistent(self):
        self.audit.verify_all()

    def test_archived_timing_parser_rejects_bad_rows(self):
        valid = "first_train 2\nsecond_train 1.5\ntrain 1\nencode 0.5\ndecode 0.1\n"
        for bad in (valid.replace("second_train", "first_train"), valid.replace("0.5", "nan"),
                    valid.replace("0.5", "0"), valid + "decode 1\n"):
            with self.subTest(stderr=bad), self.assertRaises(ValueError):
                self.audit.parse_times(bad)

    def test_archived_sample_tampering_is_rejected(self):
        report = json.loads((self.directory / "comparison.json").read_text())
        changed = copy.deepcopy(report)
        mode = next(iter(changed["samples"]))
        changed["samples"][mode][0]["encode_seconds"] *= 2
        with self.assertRaises(ValueError):
            self.audit.check_series(changed, report["oracle_sha256"], list(report["samples"]), 5)


if __name__ == "__main__":
    unittest.main()
