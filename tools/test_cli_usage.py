"""The compiler's command line: help, unknown commands and arguments a command ignores.

The default suite needs no LLVM and runs the hosted compiler. PYSTACHY_TEST_COMPILER
selects a native executable; PYSTACHY_TEST_LLVM adds a run whose arguments must
reach the program unchanged.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = os.environ.get("PYSTACHY_TEST_COMPILER", "")
LLVM = os.environ.get("PYSTACHY_TEST_LLVM", "")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pystachy-cli-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "g.py"
        self.source.write_text("import sys\nprint(sys.argv[1:])\n")

    def pystachy(self, *args, llvm=""):
        command = [COMPILER] if COMPILER else [sys.executable, "-B", str(ROOT / "pystachy.py")]
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env["PYSTACHY_CACHE"] = str(self.root / "cache")
        if llvm:
            env["PYSTACHY_LLVM"] = llvm
        return subprocess.run(command + list(args), cwd=self.root, env=env, capture_output=True,
                              text=True, timeout=600)

    def test_help_prints_usage_to_stdout_and_succeeds(self):
        for args in (["--help"], ["-h"], ["help"], ["--help", "extra"],
                     *[[cmd, flag] for cmd in ("run", "build", "ext", "ir", "check", "rt")
                       for flag in ("--help", "-h")]):
            with self.subTest(args=args):
                result = self.pystachy(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertTrue(result.stdout.startswith("usage: pystachy run FILE.py"), result.stdout)
                self.assertIn("pystachy --help", result.stdout)
                self.assertIn("docs/internals.md#environment-variables", result.stdout)

    def test_a_file_named_like_help_is_still_compiled(self):
        (self.root / "--help").write_text("print(1)\n")
        result = self.pystachy("check", "--help")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_misuse_names_the_problem_then_prints_usage_to_stderr(self):
        for args, first in (([], "usage: pystachy run FILE.py"),
                            (["frob", "g.py"], "pystachy: error: unknown command 'frob'"),
                            (["frob"], "pystachy: error: unknown command 'frob'"),
                            (["build"], "pystachy build: error: missing the source file")):
            with self.subTest(args=args):
                result = self.pystachy(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr.startswith(first + ("" if args == [] else "\n")), result.stderr)
                self.assertIn("usage: pystachy run FILE.py [ARGS...]", result.stderr)

    def test_missing_file_is_unchanged(self):
        result = self.pystachy("build", "missing.py")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "missing.py:0: error: file not found\n")

    def test_ignored_arguments_warn_and_the_command_still_succeeds(self):
        result = self.pystachy("ir", "g.py", "-O3", "-o")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("define ", result.stdout)
        self.assertEqual(result.stderr, "pystachy ir: warning: ignoring argument '-O3'\n"
                                        "pystachy ir: warning: ignoring argument '-o'\n")
        output = self.root / "g.ll"
        result = self.pystachy("ir", "g.py", "-o", str(output))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertIn("define ", output.read_text())
        result = self.pystachy("check", "g.py", "other.py")
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(result.stderr, "pystachy check: warning: ignoring argument 'other.py'\n")
        result = self.pystachy("check", "g.py")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    @unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to run programs")
    def test_run_passes_every_later_argument_to_the_program(self):
        result = self.pystachy("run", "g.py", "-O3", "--help", "-o", "x", llvm=LLVM)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, "['-O3', '--help', '-o', 'x']\n")


if __name__ == "__main__":
    unittest.main()
