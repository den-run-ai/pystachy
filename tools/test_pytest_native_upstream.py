"""Independent original-unittest controls for upstream pytest qualification."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cpython_test_methods as extractor
import pytest_native_upstream as upstream


SOURCE = '''import unittest
class Cases(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(1, 1)
    def test_wrong(self):
        self.assertEqual(1, 2)
    def test_subtests(self):
        for number in [1, 2]:
            with self.subTest(number=number):
                self.assertEqual(number, 1)
    @unittest.skip("explicit")
    def test_skip(self):
        pass
class Cleanup(unittest.TestCase):
    def test_cleanup(self):
        pass
    def tearDown(self):
        raise RuntimeError("cleanup must fail")
'''


class OriginalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "original.py"
        self.source.write_text(SOURCE)

    def original(self, selected):
        request = self.root / "request.json"
        report = self.root / "report.json"
        request.write_text(json.dumps({"source": str(self.source), "selected": selected, "imports": []}))
        ran = subprocess.run([sys.executable, "-I", "-B", str(Path(upstream.__file__)), "_original",
                              str(request), str(report)], capture_output=True, text=True, timeout=30,
                             env=upstream.environment())
        self.assertTrue(report.exists(), ran.stderr)
        result = json.loads(report.read_text())
        self.assertEqual(ran.returncode, result["exit_code"])
        return result

    def test_original_inventory_is_not_derived_from_extraction(self):
        result = self.original(["Cases.test_pass"])
        self.assertEqual(result["inventory"], ["Cases.test_pass", "Cases.test_skip", "Cases.test_subtests",
                                                "Cases.test_wrong", "Cleanup.test_cleanup"])
        upstream.validate_original(result, ["Cases.test_pass"], upstream.sha256(self.source), result["inventory"])

    def test_wrong_assertions_subtest_failures_cleanup_and_skips_do_not_qualify(self):
        for name, outcome in [("Cases.test_wrong", "failed"), ("Cases.test_subtests", "failed"),
                              ("Cleanup.test_cleanup", "error"), ("Cases.test_skip", "skipped")]:
            with self.subTest(case=name):
                result = self.original([name])
                self.assertEqual(result["exit_code"], 1)
                self.assertEqual(result["outcomes"][0]["outcome"], outcome)
                with self.assertRaises(ValueError):
                    upstream.validate_original(result, [name], upstream.sha256(self.source), result["inventory"])

    def test_expected_failures_unexpected_successes_and_setup_errors_do_not_qualify(self):
        self.source.write_text(SOURCE + '''
class Expected(unittest.TestCase):
    @unittest.expectedFailure
    def test_expected_failure(self):
        self.assertEqual(1, 2)
    @unittest.expectedFailure
    def test_unexpected_success(self):
        pass
class Setup(unittest.TestCase):
    def setUp(self):
        raise ValueError("setup must fail")
    def test_setup(self):
        pass
class ClassSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise ValueError("class setup must fail")
    def test_class_setup(self):
        pass
''')
        for name, outcome in [("Expected.test_expected_failure", "xfailed"),
                              ("Expected.test_unexpected_success", "xpassed"), ("Setup.test_setup", "error"),
                              ("ClassSetup.test_class_setup", None)]:
            with self.subTest(case=name):
                result = self.original([name])
                self.assertEqual(result["exit_code"], 1)
                if outcome:
                    self.assertEqual(result["outcomes"][0]["outcome"], outcome)
                else:
                    self.assertEqual(result["outcomes"], [])
                    self.assertEqual(result["tests_run"], 0)
                    self.assertTrue(result["errors"])
                with self.assertRaises(ValueError):
                    upstream.validate_original(result, [name], upstream.sha256(self.source), result["inventory"])

    def test_module_setup_failure_cannot_pass_an_empty_result(self):
        self.source.write_text(SOURCE + "\ndef setUpModule():\n    raise RuntimeError('module setup')\n")
        result = self.original(["Cases.test_pass"])
        self.assertEqual(result["tests_run"], 0)
        self.assertEqual(result["outcomes"], [])
        self.assertTrue(result["errors"])
        with self.assertRaises(ValueError):
            upstream.validate_original(result, ["Cases.test_pass"], upstream.sha256(self.source), result["inventory"])

    def test_custom_collection_is_in_the_recorded_original_inventory(self):
        self.source.write_text(SOURCE + '''
def load_tests(loader, tests, pattern):
    class Extra(unittest.TestCase):
        def runTest(self):
            raise RuntimeError("not selected")
    tests.addTest(Extra())
    return tests
''')
        result = self.original(["Cases.test_pass"])
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(any("Extra.runTest" in name for name in result["inventory"]))

    def test_missing_or_reordered_original_cases_and_changed_hash_fail_closed(self):
        result = self.original(["Cases.test_pass"])
        for field, value in [("complete", False), ("inventory", []), ("outcomes", []),
                             ("selected", []), ("source_sha256", "0" * 64), ("tests_run", 0)]:
            with self.subTest(field=field):
                changed = copy.deepcopy(result)
                changed[field] = value
                with self.assertRaises(ValueError):
                    upstream.validate_original(changed, ["Cases.test_pass"], upstream.sha256(self.source),
                                               result["inventory"])


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.source = self.cache / "original.py"
        self.source.write_text("import unittest\nclass Cases(unittest.TestCase):\n"
                               "    def test_pass(self):\n        self.assertEqual(1, 1)\n")
        self.spec = {"source": "original.py", "files": ["original.py"], "selected": ["Cases.test_pass"],
                     "inventory": ["Cases.test_pass"], "exclusion_reason": "explicit test selection"}
        self.manifest = {"files": {"original.py": {"sha256": upstream.sha256(self.source)}}}
        self.args = argparse.Namespace(source_cache=self.cache, fetch=False, python=sys.executable,
                                       compiler="unused", mode=["python"], work_dir=self.root / "work", timeout=30)

    def test_complete_original_adapted_generated_chain_passes(self):
        row = upstream.qualify("sample", self.spec, self.manifest, self.args)
        self.assertEqual(row["state"], "passed", row)
        self.assertEqual(row["mapping"], [{"original": "Cases.test_pass",
                                         "adapted": "test_selected.py::test_Cases__test_pass"}])
        self.assertEqual([item["mode"] for item in row["modes"]], ["python"])

    def test_false_extraction_is_rejected_against_independent_original(self):
        original_export = extractor.pytest_suite
        def altered_export(*args, **kwargs):
            result = original_export(*args, **kwargs)
            helper = Path(args[1]) / "_unittest_cases.py"
            helper.write_text(helper.read_text().replace("assert 1 == 1", "assert 1 == 2"))
            return result
        with patch.object(extractor, "pytest_suite", side_effect=altered_export):
            row = upstream.qualify("bad-adapter", self.spec, self.manifest, self.args)
        self.assertEqual(row["state"], "error")
        self.assertEqual(row["original"]["exit_code"], 0)
        self.assertEqual(row["modes"][0]["exit_code"], 1)

    def test_original_failure_is_checked_before_any_passing_adapter(self):
        self.source.write_text(self.source.read_text().replace("self.assertEqual(1, 1)", "self.assertEqual(1, 2)"))
        self.manifest["files"]["original.py"]["sha256"] = upstream.sha256(self.source)
        with patch.object(extractor, "pytest_suite") as adapt:
            row = upstream.qualify("original-fails", self.spec, self.manifest, self.args)
        adapt.assert_not_called()
        self.assertEqual(row["state"], "error")
        self.assertEqual(row["original"]["exit_code"], 1)
        self.assertEqual(row["modes"], [])

    def test_source_mismatch_is_rejected_before_import(self):
        self.source.write_text("raise RuntimeError('should not run')\n")
        row = upstream.qualify("changed", self.spec, self.manifest, self.args)
        self.assertEqual(row["state"], "error")
        self.assertIn("source hash mismatch", row["error"])
        self.assertNotIn("original", row)

    def test_cached_extras_and_bytecode_cannot_enter_source_snapshot(self):
        self.source.write_text("import value_source\n" + self.source.read_text().replace(
            "self.assertEqual(1, 1)", "self.assertEqual(value_source.VALUE, 1)"))
        helper = self.cache / "value_source.py"
        helper.write_text("VALUE = 1\n")
        self.manifest["files"]["original.py"]["sha256"] = upstream.sha256(self.source)
        self.manifest["files"]["value_source.py"] = {"sha256": upstream.sha256(helper)}
        self.spec["files"].append("value_source.py")
        self.spec.update(original_imports=["."], adapted_imports=["."],
                         reference_modules={"value_source": "value_source.py"})
        (self.cache / "shadow.py").write_text("raise RuntimeError('not pinned')\n")
        (self.cache / "original.pyc").write_bytes(b"untrusted bytecode")
        # Extension modules win over .py during normal imports from this cache.
        (self.cache / "value_source.so").write_bytes(b"untrusted extension")
        row = upstream.qualify("snapshot", self.spec, self.manifest, self.args)
        self.assertEqual(row["state"], "passed", row)
        snapshot = Path(row["source_snapshot"])
        self.assertEqual(sorted(path.name for path in snapshot.iterdir()), ["original.py", "value_source.py"])
        self.assertEqual(row["original"]["reference_modules"], {
            "value_source": {"path": str(snapshot / "value_source.py"), "sha256": upstream.sha256(helper)}})

    def test_original_implementation_must_match_the_pinned_module(self):
        self.source.write_text("import value_source\n" + self.source.read_text())
        helper = self.cache / "value_source.py"
        helper.write_text("VALUE = 1\n")
        self.manifest["files"]["original.py"]["sha256"] = upstream.sha256(self.source)
        self.manifest["files"]["value_source.py"] = {"sha256": upstream.sha256(helper)}
        self.spec["files"].append("value_source.py")
        self.spec.update(original_imports=["."], reference_modules={"value_source": "original.py"})
        row = upstream.qualify("wrong-module", self.spec, self.manifest, self.args)
        self.assertEqual(row["state"], "error")
        self.assertIn("unexpected path: value_source", row["original_process"]["stderr"])
        self.assertEqual(row["modes"], [])

    def test_environment_cannot_disable_assertions_or_override_imports(self):
        with patch.dict(os.environ, {"PYTHONOPTIMIZE": "2", "PYTHONPATH": "wrong", "PYTEST_PLUGINS": "wrong",
                                     "PYSTACHY_PATH": "wrong", "PYSTACHY_PYTHON_INT": "1"}):
            env = upstream.environment([self.root])
        self.assertNotIn("PYTHONOPTIMIZE", env)
        self.assertNotIn("PYTEST_PLUGINS", env)
        self.assertNotIn("PYSTACHY_PYTHON_INT", env)
        self.assertEqual(env["PYTHONPATH"], str(self.root))
        self.assertEqual(env["PYSTACHY_PATH"], str(self.root))

    def test_download_hash_is_checked_before_file_is_written(self):
        self.source.unlink()
        self.manifest["files"]["original.py"]["url"] = "https://example.invalid/never-used"
        from io import BytesIO
        with patch.object(upstream, "urlopen", return_value=BytesIO(b"wrong source")):
            with self.assertRaisesRegex(ValueError, "download hash mismatch"):
                upstream.source_files(self.manifest, self.spec, self.cache, fetch=True)
        self.assertFalse(self.source.exists())


class ManifestTests(unittest.TestCase):
    def test_pinned_inventories_and_selections_have_no_implicit_holes(self):
        manifest = json.loads(upstream.MANIFEST.read_text())
        for name, spec in manifest["suites"].items():
            with self.subTest(suite=name):
                self.assertEqual(len(spec["inventory"]), len(set(spec["inventory"])))
                self.assertTrue(spec["selected"])
                self.assertEqual(len(spec["selected"]), len(set(spec["selected"])))
                self.assertLessEqual(set(spec["selected"]), set(spec["inventory"]))
                self.assertIn(spec["source"], spec["files"])
                self.assertLessEqual(set(spec.get("reference_modules", {}).values()), set(spec["files"]))
                self.assertTrue(spec["exclusion_reason"])
                for key in spec["files"]:
                    entry = manifest["files"][key]
                    self.assertRegex(entry["sha256"], r"^[a-f0-9]{64}$")
                    if "local" in entry:
                        self.assertEqual(upstream.sha256(upstream.ROOT / entry["local"]), entry["sha256"])
        self.assertEqual({name: len(spec["inventory"]) for name, spec in manifest["suites"].items()},
                         {"fnmatch": 17, "textwrap": 66, "statistics": 401, "mypyc-namegen": 5, "mypyc-literals": 11,
                          "mypy-stubinfo": 2})


if __name__ == "__main__":
    unittest.main()
