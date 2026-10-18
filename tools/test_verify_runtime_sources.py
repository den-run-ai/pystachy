"""Keep compiler cache coverage independent of its declared input manifest."""
from pathlib import Path
import tempfile
import unittest

from check_runtime import compiler_source_problems


class CompilerSourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sources = ["src/driver.py", "src/parser/literals.py",
                        "lib/_pystachy_unicodedata_names.py"]
        for name in self.sources + ["lib/unrelated.py"]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic compiler input\n")

    def problems(self, sources):
        return compiler_source_problems(self.root, sources)

    def test_components_and_names_table_are_complete(self):
        self.assertEqual(self.problems(self.sources), [])

    def test_omitted_names_table_is_rejected(self):
        self.assertEqual(self.problems(self.sources[:-1]), [
            "runtime cache omits compiler source: lib/_pystachy_unicodedata_names.py"])

    def test_omitted_nested_component_is_rejected(self):
        self.assertEqual(self.problems(self.sources[:1] + self.sources[2:]), [
            "runtime cache omits compiler source: src/parser/literals.py"])

    def test_new_component_is_discovered_independently(self):
        (self.root / "src/new_pass.py").write_text("# new compiler pass\n")
        self.assertEqual(self.problems(self.sources), [
            "runtime cache omits compiler source: src/new_pass.py"])

    def test_unrelated_library_is_not_a_compiler_input(self):
        self.assertEqual(self.problems(self.sources + ["lib/unrelated.py"]), [
            "runtime cache names missing compiler source: lib/unrelated.py"])

    def test_unknown_manifest_entry_is_rejected(self):
        self.assertEqual(self.problems(self.sources + ["src/removed.py"]), [
            "runtime cache names missing compiler source: src/removed.py"])

    def test_duplicate_entry_is_rejected(self):
        self.assertEqual(self.problems(self.sources + self.sources[-1:]), [
            "runtime cache repeats a compiler source path"])

    def test_missing_table_file_is_rejected(self):
        (self.root / self.sources[-1]).unlink()
        self.assertEqual(self.problems(self.sources), [
            "compiler dependency is missing: lib/_pystachy_unicodedata_names.py"])

    def test_directory_cannot_substitute_for_table(self):
        path = self.root / self.sources[-1]
        path.unlink()
        path.mkdir()
        self.assertEqual(self.problems(self.sources), [
            "compiler dependency is missing: lib/_pystachy_unicodedata_names.py"])

    def test_missing_table_and_manifest_entry_still_fail(self):
        (self.root / self.sources[-1]).unlink()
        self.assertEqual(self.problems(self.sources[:-1]), [
            "compiler dependency is missing: lib/_pystachy_unicodedata_names.py",
            "runtime cache omits compiler source: lib/_pystachy_unicodedata_names.py"])


if __name__ == "__main__":
    unittest.main()
