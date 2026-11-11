"""Keep upstream selection, source provenance and phase accounting fail closed."""
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pytest_native_json_repair as qualification


class SelectionTests(unittest.TestCase):
    def test_function_decorators_and_helper_bodies_are_preserved(self):
        source = ('import pytest\nfrom original import repair_json\n\n'
                  'def helper(value: str):\n    return value + "é"\n\n'
                  '@pytest.mark.parametrize("value", ["x", "y"], ids=["one", "two"])\n'
                  'def test_selected(value: str):\n    # assertion must survive exactly\n'
                  '    assert helper(value) == value + "é"\n\n'
                  'def test_excluded():\n    assert False\n')
        adapted, hashes = qualification.extract(source, ["test_selected"], ["helper"])
        expected = source[source.index('@pytest.mark.parametrize'):source.index('\ndef test_excluded')].rstrip() + '\n'
        self.assertIn(expected, adapted)
        self.assertEqual(hashes["test_selected"], hashlib.sha256(expected.encode()).hexdigest())
        self.assertIn('def helper(value: str):\n    return value + "é"', adapted)
        self.assertNotIn("test_excluded", adapted)

    def test_unknown_duplicate_or_empty_selections_fail(self):
        source = "def test_a():\n    assert True\n"
        for selected in ([], ["missing"], ["test_a", "test_a"]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                qualification.extract(source, selected)

    def test_helpers_cannot_add_another_test_or_be_missing(self):
        source = "def test_a():\n    assert True\n"
        for helpers in (["missing"], ["test_a"]):
            with self.subTest(helpers=helpers), self.assertRaises(ValueError):
                qualification.extract(source, ["test_a"], helpers)

    def test_helper_refinement_is_limited_to_argument_annotation(self):
        source = ('def helper(expected: dict):\n    assert expected == {"a": "b"}\n'
                  'def test_a():\n    helper({"a": "b"})\n')
        refinement = {"function": "helper", "before": "expected: dict", "after": "expected: dict[str, str]"}
        adapted, hashes = qualification.extract(source, ["test_a"], ["helper"], [refinement])
        self.assertIn('expected: dict[str, str]', adapted)
        self.assertIn('assert expected == {"a": "b"}', adapted)
        self.assertEqual(set(hashes), {"helper", "test_a"})
        wrong = {"function": "helper", "before": '"a": "b"', "after": '"a": "wrong"'}
        with self.assertRaisesRegex(ValueError, "more than argument annotations"):
            qualification.extract(source, ["test_a"], ["helper"], [wrong])


class OutcomeTests(unittest.TestCase):
    def evidence(self):
        case = "tests/test_a.py::test_a"
        return {"exit_code": 0, "cases": [case], "events": [
            {"nodeid": case, "phase": phase, "outcome": "passed", "detail": ""}
            for phase in ("setup", "call", "teardown")]}

    def test_complete_original_passes_and_relocation_is_exact(self):
        evidence = self.evidence()
        qualification.require_pass(evidence)
        adapted = qualification.remap(evidence)
        self.assertEqual(adapted["cases"], ["test_a.py::test_a"])
        self.assertEqual(evidence["cases"], ["tests/test_a.py::test_a"])

    def test_missing_duplicate_or_skipped_cases_do_not_qualify(self):
        good = self.evidence()
        mutations = []
        missing = copy.deepcopy(good)
        missing["events"].pop(1)
        mutations.append(missing)
        duplicate = copy.deepcopy(good)
        duplicate["cases"] *= 2
        mutations.append(duplicate)
        for outcome in ("failed", "skipped", "xfailed", "xpassed"):
            changed = copy.deepcopy(good)
            changed["events"][1]["outcome"] = outcome
            mutations.append(changed)
        for bad in mutations:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                qualification.require_pass(bad)

    def test_empty_collection_and_nonzero_process_fail(self):
        for evidence in ({"exit_code": 0, "cases": [], "events": []},
                         {**self.evidence(), "exit_code": 1}):
            with self.assertRaises(ValueError):
                qualification.require_pass(evidence)

    def test_relocation_does_not_normalize_arbitrary_case_paths(self):
        with self.assertRaisesRegex(ValueError, "unexpected original"):
            qualification.remap({"cases": ["elsewhere/test_a.py::test_a"], "events": []})

    def test_inherited_configuration_cannot_change_qualification(self):
        with patch.dict(os.environ, {"PYTHONOPTIMIZE": "2", "PYTHONTRACEMALLOC": "1",
                                     "PYTEST_ADDOPTS": "-x", "PYSTACHY_OPT": "0",
                                     "PYSTACHY_LLVM": "/toolchain", "LD_LIBRARY_PATH": "/libs"}):
            env = qualification.clean_environment([Path("/explicit")])
        self.assertNotIn("PYTHONOPTIMIZE", env)
        self.assertNotIn("PYTHONTRACEMALLOC", env)
        self.assertNotIn("PYTEST_ADDOPTS", env)
        self.assertNotIn("PYSTACHY_OPT", env)
        self.assertEqual(env["PYSTACHY_LLVM"], "/toolchain")
        self.assertEqual(env["LD_LIBRARY_PATH"], "/libs")


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pytest-json-source-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        (self.upstream / "tests").mkdir()
        (self.upstream / "src").mkdir()
        (self.upstream / "LICENSE").write_text("test license\n")
        (self.upstream / "tests/test_a.py").write_text("def test_a():\n    assert True\n")
        (self.upstream / "src/library.py").write_text("VALUE = 1\n")
        (self.upstream / ".gitignore").write_text("ignored/\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        self.manifest = {"commit": self.git("rev-parse", "HEAD").strip(),
                         "source_sha256": {"src/library.py": qualification.digest(self.upstream / "src/library.py")},
                         "test_sha256": {"test_a.py": qualification.digest(self.upstream / "tests/test_a.py")}}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.upstream), *args], text=True)

    def verify(self):
        with patch.object(qualification, "CORPUS", self.upstream):
            return qualification.verify_source(self.upstream, self.manifest)

    def test_pristine_pin_records_every_source(self):
        evidence = self.verify()
        self.assertEqual(set(evidence["source_sha256"]), {"src/library.py", "tests/test_a.py"})

    def test_modified_or_wrong_pin_is_rejected(self):
        self.manifest["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "commit"):
            self.verify()
        self.manifest["commit"] = self.git("rev-parse", "HEAD").strip()
        (self.upstream / "src/library.py").write_text("VALUE = 2\n")
        with self.assertRaisesRegex(ValueError, "modified"):
            self.verify()

    def test_ignored_importable_source_cannot_escape_accounting(self):
        (self.upstream / "ignored").mkdir()
        (self.upstream / "ignored/extra.py").write_text("VALUE = 1\n")
        with self.assertRaisesRegex(ValueError, "ignored Python source"):
            self.verify()

    def test_ignored_bytecode_or_extensions_cannot_supply_the_oracle(self):
        (self.upstream / "ignored").mkdir()
        for suffix in (".pyc", ".pyo", ".so", ".pyd"):
            path = self.upstream / ("ignored/extra" + suffix)
            path.write_bytes(b"stale importable artifact")
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "compiled import artifacts"):
                self.verify()
            path.unlink()


if __name__ == "__main__":
    unittest.main()
