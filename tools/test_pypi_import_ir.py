"""A root-wheel IR result must be attributable to that wheel's Python source."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pypi_import_ir as ir


class WheelImportTests(unittest.TestCase):
    def row(self, wheelhouse, entries, module):
        wheel = wheelhouse / "project.whl"
        with zipfile.ZipFile(wheel, "w") as z:
            for name in entries:
                z.writestr(name, "pass\n")
        return {"filename": wheel.name, "import": module, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}

    def test_absent_colliding_and_ambiguous_modules_never_compile(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ir, "compile_ir") as compile_ir:
            for entries, module in ((["other.py"], "absent"), (["json.py"], "json"),
                                    (["dual.py", "dual/__init__.py"], "dual")):
                row = self.row(Path(tmp), entries, module)
                self.assertIn("exclusion", ir.probe(row, Path(tmp), {"pre": (None, {})}, 1))
            compile_ir.assert_not_called()

    def test_hash_and_unsafe_zip_paths_fail_before_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("../escape.py", "pkg/../../escape.py", "/escape.py", "C:/escape.py", "dir\\escape.py", "p.data/purelib/C:/escape.py"):
                row = self.row(Path(tmp), [name], "project")
                with self.assertRaisesRegex(ValueError, "unsafe wheel entry"):
                    ir.probe(row, Path(tmp), {}, 1)
            row = self.row(Path(tmp), ["pkg.py"], "pkg") | {"sha256": "0" * 64}
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                ir.probe(row, Path(tmp), {}, 1)

    def test_control_reaches_exact_wheel_file_and_restores_source_between_compilers(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self.row(Path(tmp), ["dist.data/purelib/pkg/__init__.py"], "pkg")
            builds = {name: (name, {}) for name in ("correct", "wrong-origin", "wrong-error", "next")}
            def compile_ir(compiler, env, driver, timeout):
                source = Path(env["PYSTACHY_PATH"], "pkg/__init__.py").read_bytes()
                if source == b"pass\n" or compiler == "wrong-origin":
                    return {"status": "ir"}
                self.assertEqual(source, b"if :\n")
                module = "other.py" if compiler == "wrong-error" else "pkg/__init__.py"
                return {"status": "rejected", "exit": 1, "diagnostic": f"WHEEL/{module}:1: error: invalid syntax"}
            with patch.object(ir, "compile_ir", side_effect=compile_ir):
                results = ir.probe(row, Path(tmp), builds, 1)["outcomes"]
            self.assertEqual([r["status"] for r in results.values()], ["ir", "unattributed", "unattributed", "ir"])

    def test_successful_process_without_fresh_ir_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            driver = root / "probe.py"
            driver.with_suffix(".ll").write_text("old IR")
            env = {"PYSTACHY_PATH": str(root / "wheel"), "PYSTACHY_HOME": str(root / "compiler")}
            result = ir.compile_ir("/bin/true", env, driver, 2)
            self.assertEqual(result["status"], "process-error")
            self.assertIn("nonempty IR", result["diagnostic"])


if __name__ == "__main__":
    unittest.main()
