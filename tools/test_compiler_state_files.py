"""Each hosted/runtime/restart load owns a fresh, coordinated file-index space."""
from contextlib import redirect_stderr
import inspect
import io
from pathlib import Path
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from compiler_state_probe import ROOT
from src.pystachy_compiler import diagnostics, driver, loader
from src.pystachy_compiler.diagnostics import Rejoin
from src.pystachy_compiler.specs import GLUE, SPECSHOW
from src.pystachy_compiler.syntax import LAMBDAS


class FileStateTests(unittest.TestCase):
    # Preserve the surrounding test process: these tests intentionally leave a
    # completed or rejected compilation's discoveries visible between calls.
    def setUp(self):
        self.roots = [diagnostics.FILES, diagnostics.DYNFILES, diagnostics.INTFILES, diagnostics.INTSPANS, LAMBDAS,
                      driver.RENAMED, driver.LIBS, driver.LINKDL, GLUE, SPECSHOW]
        self.saved = [value.copy() for value in self.roots]
        self.source = diagnostics.SRC
        diagnostics.SRC = "hosted-context.py"

    def tearDown(self):
        for target, saved in zip(self.roots, self.saved):
            target.clear()
            if isinstance(target, list):
                target.extend(saved)
            else:
                target.update(saved)
        diagnostics.SRC = self.source

    def compile(self, source, path="main.py", dirs=(), runtime=False):
        messages = io.StringIO()
        with redirect_stderr(messages):
            try:
                ir = (driver.runtime_ir(path, source, False) if runtime else
                      driver.compile_program(path, source, list(dirs), ""))
                result = (0, ir, messages.getvalue())
            except SystemExit as error:
                result = (error.code, "", messages.getvalue())
        self.assertEqual(diagnostics.SRC, "hosted-context.py")
        return result

    def file_contract(self, program):
        diagnostics.FILES[:] = ["old-main.py", "old-import.py"]
        diagnostics.DYNFILES.clear()
        diagnostics.DYNFILES.update({0: True, 1: True, 5: True})
        diagnostics.INTFILES.clear()
        diagnostics.INTFILES.update({0: True, 1: True, 5: True})
        diagnostics.INTSPANS[:] = [[1, 9]]
        instance = loader.Loader([])
        program(instance, "plain.py", "print(1)\n")
        self.assertEqual(diagnostics.FILES, ["plain.py"])
        self.assertEqual(diagnostics.DYNFILES, {})
        self.assertEqual(diagnostics.INTFILES, {})
        self.assertEqual(diagnostics.INTSPANS, [])
        instance = loader.Loader([])
        program(instance, "dynamic.py", "# pystachy: dynamic-any\nprint(1)\n")
        self.assertEqual(diagnostics.FILES, ["dynamic.py"])
        self.assertEqual(diagnostics.DYNFILES, {0: True})
        self.assertEqual(diagnostics.INTFILES, {})
        instance = loader.Loader([])
        program(instance, "promoting.py", "# pystachy: python-int\nprint(1)\n")
        self.assertEqual(diagnostics.FILES, ["promoting.py"])
        self.assertEqual(diagnostics.DYNFILES, {})
        self.assertEqual(diagnostics.INTFILES, {0: True})

    def test_program_replaces_both_tables(self):
        self.file_contract(loader.Loader.program)

    def test_each_missing_reset_is_detected(self):
        source = textwrap.dedent(inspect.getsource(loader.Loader.program))
        for reset in ("FILES.clear()", "DYNFILES.clear()", "INTFILES.clear()", "INTSPANS.clear()"):
            with self.subTest(reset=reset):
                statement = "    " + reset + "\n"
                self.assertEqual(source.count(statement), 1)
                namespace = dict(vars(loader))
                exec(compile(source.replace(statement, "    pass\n"), "<missing-file-reset>", "exec"), namespace)
                with self.assertRaises(AssertionError):
                    self.file_contract(namespace["program"])

    def test_both_opt_in_directions_after_success_and_failure(self):
        box = ("from typing import Any\nclass Box:\n"
               "    def __init__(self):\n        self.value: Any = None\nBox()\n")
        targets = (box, "# pystachy: dynamic-any\n" + box)
        prefixes = ("print(1)\n", "# pystachy: dynamic-any\nprint(1)\n",
                    "unknown\n", "# pystachy: dynamic-any\nunknown\n",
                    "# pystachy: dynamic-any\n!\n")
        for target in targets:
            # Only the reference begins in explicitly empty state. No clearing
            # may hide the production boundary between the two tested calls.
            diagnostics.FILES.clear()
            diagnostics.DYNFILES.clear()
            expected = self.compile(target)
            self.assertEqual(expected[0], 0 if target.startswith("#") else 1)
            for first in prefixes:
                with self.subTest(dynamic=target.startswith("#"), first=first):
                    self.compile(first, "previous.py")
                    self.assertEqual(self.compile(target), expected)
                    self.assertEqual(diagnostics.FILES, ["main.py"])
                    self.assertEqual(diagnostics.DYNFILES, {0: True} if target.startswith("#") else {})

    def test_import_opt_ins_and_diagnostics_are_reindexed(self):
        with tempfile.TemporaryDirectory() as temp:
            module = Path(temp) / "dependency.py"
            source = "import dependency\nprint(dependency.value)\n"
            dirs = [temp, str(ROOT / "lib")]
            for dynamic in (True, False, True):
                module.write_text(("# pystachy: dynamic-any\n" if dynamic else "") + "value = 3\n")
                self.assertEqual(self.compile(source, dirs=dirs)[0], 0)
                self.assertEqual(diagnostics.FILES, ["main.py", str(module)])
                self.assertEqual(diagnostics.DYNFILES, {1: True} if dynamic else {})
            module.write_text("missing_name\n")
            failed = self.compile(source, dirs=dirs)
            self.assertEqual(failed[0], 1)
            self.assertIn(f"{module}:1: error:", failed[2])
            self.assertEqual(diagnostics.DYNFILES, {})

    def test_import_int_opt_ins_are_reindexed(self):
        with tempfile.TemporaryDirectory() as temp:
            module = Path(temp) / "dependency.py"
            source = "import dependency\nprint(dependency.value)\n"
            dirs = [temp, str(ROOT / "lib")]
            for promoting in (True, False, True):
                module.write_text(("# pystachy: python-int\nvalue = 2 ** 64\n" if promoting else "value = 3\n"))
                self.assertEqual(self.compile(source, dirs=dirs)[0], 0)
                self.assertEqual(diagnostics.FILES, ["main.py", str(module)])
                self.assertEqual(diagnostics.INTFILES, {1: True} if promoting else {})
            module.write_text("# pystachy: python-int\n# pystachy: dynamic-any\nvalue = 3\n")
            failed = self.compile(source, dirs=dirs)
            self.assertEqual(failed[0], 1)
            self.assertIn("cannot opt in to both dynamic Any and promoting ints", failed[2])
            # (a program compiled after one that opts in keeps 64-bit ints)
            self.assertIn("@pys_big_op", self.compile("# pystachy: python-int\nvalue = 2 ** 64\nprint(value)\n")[1])
            plain = self.compile("value = 2 ** 64\nprint(value)\n")
            self.assertEqual(plain[0], 0)
            self.assertNotIn("@pys_big_", plain[1])
            self.assertEqual(diagnostics.INTFILES, {})

    def test_restart_rebuilds_file_indices_and_opt_ins(self):
        original = driver.Gen.program
        passes = []

        def restart_once(gen, modules):
            passes.append((diagnostics.FILES.copy(), diagnostics.DYNFILES.copy()))
            if len(passes) == 1:
                diagnostics.FILES.append("abandoned.py")
                diagnostics.DYNFILES[5] = True
                raise Rejoin()
            return original(gen, modules)

        with tempfile.TemporaryDirectory() as temp:
            module = Path(temp) / "dependency.py"
            module.write_text("# pystachy: dynamic-any\nvalue = 3\n")
            with patch.object(driver.Gen, "program", restart_once):
                result = self.compile("import dependency\nprint(dependency.value)\n",
                                      dirs=[temp, str(ROOT / "lib")])
            self.assertEqual(result[0], 0)
            self.assertEqual(passes, [(["main.py", str(module)], {1: True})] * 2)

    def test_runtime_program_interleaving_and_failures(self):
        runtime = "def pys_probe(a: int) -> int:\n    return a + 1\n"
        diagnostics.FILES.clear()
        diagnostics.DYNFILES.clear()
        expected = self.compile(runtime, "runtime-probe.py", runtime=True)
        self.assertEqual(expected[0], 0)
        for first in ("# pystachy: dynamic-any\nprint(1)\n",
                      "# pystachy: dynamic-any\nunknown\n"):
            with self.subTest(first=first):
                self.compile(first, "previous.py")
                self.assertEqual(self.compile(runtime, "runtime-probe.py", runtime=True), expected)
                self.assertEqual(diagnostics.FILES, ["runtime-probe.py"])
                self.assertEqual(diagnostics.DYNFILES, {})
                self.assertEqual(self.compile("unknown\n", "bad-runtime.py", runtime=True)[0], 1)
                self.assertEqual(self.compile("# pystachy: dynamic-any\nprint(1)\n")[0], 0)
                failed = self.compile("unknown\n")
                self.assertEqual(failed[0], 1)
                self.assertIn("hosted-context.py:1: error:", failed[2])
                self.assertEqual(diagnostics.FILES, ["main.py"])
                self.assertEqual(diagnostics.DYNFILES, {})


if __name__ == "__main__":
    unittest.main()
