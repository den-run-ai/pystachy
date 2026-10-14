"""Online runtime imports must expose code to LLVM without copying host state."""
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.driver import llvm_dir
from src.pystachy_compiler.online import online_runtime_import, online_runtime_symbols


RUNTIME = """
@counter = internal global i64 3
@literal = private constant i64 4
define internal i64 @safe_private(i64 %x) {
  %y = add i64 %x, 1
  ret i64 %y
}
define internal i64 @unsafe_private() {
  %x = load i64, ptr @counter
  ret i64 %x
}
define i64 @pure(i64 %x) {
  %y = call i64 @safe_private(i64 %x)
  ret i64 %y
}
define dso_local i64 @stateful() {
  %x = load i64, ptr @counter
  ret i64 %x
}
define i64 @wrapper() {
  %x = call i64 @stateful()
  ret i64 %x
}
define i64 @transitive() {
  %x = call i64 @unsafe_private()
  ret i64 %x
}
define ptr @identity() {
  ret ptr @safe_private
}
define i64 @constant_reader() {
  %x = load i64, ptr @literal
  ret i64 %x
}
define weak i64 @overridable(i64 %x) {
  ret i64 %x
}
"""


class RuntimeImportTests(unittest.TestCase):
    def test_storage_and_unsafe_private_dependencies_never_enter_the_image(self):
        imported = online_runtime_import(RUNTIME)
        self.assertFalse(any(row.startswith("@") for row in imported.splitlines()))
        self.assertIn("define available_externally i64 @pure(", imported)
        self.assertIn("define internal i64 @safe_private(", imported)
        for name in ["stateful", "transitive", "identity", "constant_reader", "overridable"]:
            self.assertFalse(any(row.startswith("define ") and f"@{name}(" in row
                                 for row in imported.splitlines()), name)
            self.assertTrue(any(row.startswith("declare ") and f"@{name}(" in row
                                for row in imported.splitlines()), name)
        self.assertNotIn("@unsafe_private", imported)
        self.assertNotIn("dso_local", imported)

    def test_public_stateful_callees_remain_host_boundaries(self):
        imported = online_runtime_import(RUNTIME)
        self.assertIn("define available_externally i64 @wrapper()", imported)
        self.assertIn("declare i64 @stateful()", imported)
        self.assertIn("call i64 @stateful()", imported)

    def test_a_private_callee_cannot_also_escape_as_its_argument(self):
        imported = online_runtime_import("""
define internal i64 @helper(ptr %callback) {
  ret i64 1
}
define i64 @escape() {
  %x = call i64 @helper(ptr @helper)
  ret i64 %x
}
""")
        self.assertIn("declare i64 @escape()", imported)
        self.assertNotIn("define available_externally i64 @escape()", imported)

    def test_symbol_reader_ignores_comments_and_strings_but_rejects_quoted_names(self):
        self.assertEqual(online_runtime_symbols('  call void @print(ptr @text) ; @comment'),
                         ["print", "text"])
        self.assertEqual(online_runtime_symbols('!0 = !{!"email@host"}'), [])
        self.assertEqual(online_runtime_symbols('  call void @"quoted name"()'), [""])

    def test_global_metadata_references_fail_closed(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            online_runtime_import(RUNTIME + '\n!0 = !{ptr @counter}\n')

    def test_llvm_inlines_imported_body_without_defining_a_second_runtime(self):
        directory = llvm_dir()
        opt = str(Path(directory) / "opt") if directory else shutil.which("opt")
        link = str(Path(directory) / "llvm-link") if directory else shutil.which("llvm-link")
        if not opt or not link or not Path(opt).is_file() or not Path(link).is_file():
            self.skipTest("LLVM is not available")
        with tempfile.TemporaryDirectory(prefix="pystachy-inline-runtime-") as temporary:
            root = Path(temporary)
            imported = root / "runtime.ll"
            imported.write_text(online_runtime_import(RUNTIME))
            program = root / "program.ll"
            program.write_text("""
declare i64 @pure(i64)
declare i64 @wrapper()
define i64 @entry(i64 %x) {
  %y = call i64 @pure(i64 %x)
  %z = call i64 @wrapper()
  %r = add i64 %y, %z
  ret i64 %r
}
""")
            combined = root / "combined.bc"
            subprocess.run([link, "--only-needed", str(program), str(imported), "-o", str(combined)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([opt, "-passes=globaldce,default<O2>,verify", "-S", str(combined), "-o", "-"],
                                    check=True, capture_output=True, text=True).stdout
            self.assertIn("add i64 %x, 1", result)
            self.assertIn("call i64 @stateful()", result)
            self.assertNotIn("call i64 @pure(", result)
            self.assertNotIn("call i64 @wrapper(", result)
            self.assertFalse(any(row.startswith("@") for row in result.splitlines()))
            self.assertFalse(any(row.startswith("define ") and "@stateful(" in row
                                 for row in result.splitlines()))


if __name__ == "__main__":
    unittest.main()
