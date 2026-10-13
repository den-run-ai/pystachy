"""Reject provenance drift and false-green upstream test runs."""
import contextlib
import copy
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import port_check as check


class PortCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write(".python-version", "3.13.16\n")
        self.write("upstream/widget.py", "def value():\n    return 17\n")
        self.write("lib/widget.py", "# Pystachy port: test fixture\ndef value():\n    return 17\n")
        self.write("upstream/test_widget.py", "import unittest\nfrom widget import value\n"
                   "class WidgetTest(unittest.TestCase):\n"
                   "    def test_value(self):\n        self.assertEqual(value(), 17)\n")
        self.identifier = "test_widget.WidgetTest.test_value"
        self.module = {"source": "upstream/widget.py", "test": "upstream/test_widget.py",
                       "port": "lib/widget.py", "adaptation": "widget.patch", "bindings": ["value"],
                       "expected_tests": 1, "expected_skips": {}, "cases": {self.identifier: {
                           "status": "unmapped", "evidence": ["upstream/test_widget.py"],
                           "reason": "Fixture has no compiled test."}}}
        self.manifest = {"schema": 1, "upstream": {"python": "3.13.16"}, "files": {},
                         "modules": {"widget": self.module}}
        for relative in ["upstream/widget.py", "upstream/test_widget.py"]:
            self.manifest["files"][relative] = {
                "upstream": relative, "sha256": hashlib.sha256((self.root / relative).read_bytes()).hexdigest()}
        self.write("widget.patch", check.adaptation_diff(self.root, self.module, self.manifest))
        for name in ["widget", "test_widget", "another_port"]:
            previous = sys.modules.get(name)
            self.addCleanup(self.restore_module, name, previous)

    @staticmethod
    def restore_module(name, previous):
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous

    def write(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def run_port(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return check.run_port(self.root, "widget", self.module)

    def test_valid_fixture_runs_local_port_and_reports_hosted_counts(self):
        check.check_sources(self.root, self.manifest)
        report = self.run_port()
        self.assertEqual((report["passed"], report["tests_run"], report["skipped"]), (1, 1, {}))
        self.assertEqual(report["mode"], "cpython_hosted")
        self.assertEqual(report["compiled_mapping"], {"unmapped": 1})

    def test_source_and_test_sha_tampering_is_rejected(self):
        for relative in self.manifest["files"]:
            with self.subTest(relative=relative):
                original = (self.root / relative).read_text()
                self.write(relative, original + "# changed\n")
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    check.check_sources(self.root, self.manifest)
                self.write(relative, original)

    def test_missing_source_or_test_pin_is_rejected(self):
        for relative in self.manifest["files"]:
            manifest = copy.deepcopy(self.manifest)
            del manifest["files"][relative]
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, "must have pinned"):
                check.check_sources(self.root, manifest)

    def test_unrecorded_port_edit_is_rejected_even_next_to_a_marker(self):
        source = (self.root / "lib/widget.py").read_text()
        self.write("lib/widget.py", source.replace("17", "18"))
        with self.assertRaisesRegex(ValueError, "adaptation diff changed"):
            check.check_sources(self.root, self.manifest)

    def test_adaptation_tampering_is_rejected(self):
        self.write("widget.patch", "")
        with self.assertRaisesRegex(ValueError, "adaptation diff changed"):
            check.check_sources(self.root, self.manifest)

    def test_unrecorded_line_ending_change_is_rejected(self):
        path = self.root / "lib/widget.py"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError, "adaptation diff changed"):
            check.check_sources(self.root, self.manifest)

    def test_wrong_python_pin_is_rejected(self):
        with mock.patch.object(check.platform, "python_version", return_value="3.13.15"):
            with self.assertRaisesRegex(ValueError, "requires CPython 3.13.16"):
                check.check_python(self.root, self.manifest)

    def test_missing_mapping_or_evidence_is_rejected(self):
        self.module["cases"] = {}
        with self.assertRaisesRegex(ValueError, "case mapping mismatch"):
            self.run_port()
        self.module["cases"] = {self.identifier: {
            "status": "unmapped", "evidence": ["missing.py"], "reason": "Missing evidence."}}
        with self.assertRaisesRegex(ValueError, "missing or non-local file"):
            self.run_port()

    def test_compiled_mapping_requires_id_and_recording(self):
        self.module["cases"][self.identifier]["status"] = "compiled"
        with self.assertRaisesRegex(ValueError, "compiled mapping needs"):
            self.run_port()
        source = (self.root / "upstream/test_widget.py").read_text()
        self.write("upstream/test_widget.py", f"# {self.identifier}\n{source}")
        self.write("upstream/test_widget.out", "")
        # An upstream unittest file plus .out is not in the compiled test corpus.
        with self.assertRaisesRegex(ValueError, "compiled mapping needs"):
            self.run_port()
        self.write("tests/upstream_widget.py", f"# {self.identifier}\nassert 17 == 17\n")
        self.module["cases"][self.identifier]["evidence"] = ["tests/upstream_widget.py"]
        with self.assertRaisesRegex(ValueError, "compiled mapping needs"):
            self.run_port()
        self.write("tests/upstream_widget.out", "")
        self.assertEqual(self.run_port()["compiled_mapping"], {"compiled": 1})

    def test_zero_tests_and_wrong_count_cannot_report_success(self):
        self.module["expected_tests"] = 2
        with self.assertRaisesRegex(ValueError, "test count changed"):
            self.run_port()
        self.write("upstream/test_widget.py", "from widget import value\n")
        self.module["expected_tests"] = 0
        self.module["cases"] = {}
        with self.assertRaisesRegex(ValueError, "empty or duplicate"):
            self.run_port()

    def test_partial_mapping_requires_compiled_evidence_too(self):
        self.module["cases"][self.identifier]["status"] = "partial"
        with self.assertRaisesRegex(ValueError, "compiled mapping needs"):
            self.run_port()

    def test_wrong_module_and_wrong_function_cannot_report_success(self):
        wrong = types.ModuleType("widget")
        wrong.__file__ = __file__
        with mock.patch.object(check, "load_file", return_value=wrong):
            with self.assertRaisesRegex(ValueError, "wrong module loaded"):
                self.run_port()
        source = (self.root / "upstream/test_widget.py").read_text()
        self.write("upstream/test_widget.py", source.replace("from widget import value", "def value(): return 17"))
        with self.assertRaisesRegex(ValueError, "tests use the wrong"):
            self.run_port()

    def test_shadowing_another_port_is_rejected(self):
        wrong = types.ModuleType("another_port")
        wrong.__file__ = str(self.root / "lib/another_port.py")
        sys.modules["another_port"] = wrong
        with self.assertRaisesRegex(ValueError, "dependency shadowed"):
            self.run_port()

    def test_failures_skips_and_expected_failures_cannot_report_success(self):
        original = (self.root / "upstream/test_widget.py").read_text()
        changes = [original.replace("value(), 17", "value(), 18"),
                   original.replace("    def test_value", "    @unittest.skip('lost coverage')\n    def test_value"),
                   original.replace("    def test_value", "    @unittest.expectedFailure\n    def test_value")
                   .replace("value(), 17", "value(), 18")]
        for source in changes:
            with self.subTest(source=source):
                self.write("upstream/test_widget.py", source)
                with self.assertRaises(ValueError):
                    self.run_port()

    def test_duplicate_manifest_keys_are_rejected(self):
        self.write("manifest.json", '{"modules": {}, "modules": {}}')
        with self.assertRaisesRegex(ValueError, "duplicate manifest key"):
            check.read_json(self.root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
