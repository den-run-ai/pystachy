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

    def pystachy(self, *args, llvm=None, path=None, cache=None, extra=None):
        command = [COMPILER] if COMPILER else [sys.executable, "-B", str(ROOT / "pystachy.py")]
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env["PYSTACHY_CACHE"] = str(self.root / "cache") if cache is None else cache
        env.update(extra or {})
        if path is not None:
            env["PATH"] = path
        if llvm is not None:
            env["PYSTACHY_LLVM"] = llvm
        return subprocess.run(command + list(args), cwd=self.root, env=env, capture_output=True,
                              text=True, timeout=600)

    def test_help_prints_usage_to_stdout_and_succeeds(self):
        for args in (["--help"], ["-h"], ["help"], ["--help", "extra"],
                     *[[cmd, flag] for cmd in ("run", "build", "ext", "ir", "check", "rt", "doctor")
                       for flag in ("--help", "-h")]):
            with self.subTest(args=args):
                result = self.pystachy(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertTrue(result.stdout.startswith("usage: pystachy run FILE.py"), result.stdout)
                self.assertIn("pystachy --help", result.stdout)
                self.assertIn("docs/internals.md#environment-variables", result.stdout)

    def test_doctor_reports_selected_llvm_without_creating_a_cache(self):
        tools = self.root / "LLVM's tools"
        tools.mkdir()
        for name in ("clang", "opt", "lli", "llvm-link", "llvm-as"):
            binary = tools / name
            binary.write_text("#!/bin/sh\n[ \"$1\" = --version ] || exit 3\n"
                              "echo 'Ubuntu LLVM version 18.1.3'\necho 'Target: x86_64-pc-linux-gnu'\n")
            binary.chmod(0o700)
        for llvm, path in ((str(tools), ""), ("", str(tools))):
            with self.subTest(llvm=llvm):
                result = self.pystachy("doctor", llvm=llvm, path=path)
                self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
                for line in (f"LLVM search: {llvm or 'PATH'}", "Target: x86_64-pc-linux-gnu",
                             f"Runtime cache: {self.root / 'cache'}", "clang: 18.1.3", "llvm-as: 18.1.3"):
                    self.assertIn(line, result.stdout.splitlines())

        (tools / "lli").unlink()
        (tools / "opt").write_text("#!/bin/sh\necho 'LLVM version 20.1.8'\n")
        result = self.pystachy("doctor", llvm=str(tools))
        self.assertEqual((result.returncode, result.stderr), (1, ""))
        self.assertIn("lli: unavailable", result.stdout)
        self.assertIn("opt: 20.1.8\n  expected LLVM major 18", result.stdout)
        self.assertFalse((self.root / "cache").exists())

    def test_doctor_names_a_relative_cache_from_the_root(self):
        here = os.path.realpath(self.root)
        missing = str(self.root / "no LLVM")
        for spelled, expected in (("rel", "rel"), ("./rel/x", "rel/x"), ("././rel", "rel")):
            with self.subTest(cache=spelled):
                result = self.pystachy("doctor", llvm=missing, cache=spelled)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"Runtime cache: {here}/{expected}", result.stdout.splitlines())
                self.assertFalse((self.root / "rel").exists())
        # A checkout's compiler run by a relative path, with no PYSTACHY_CACHE: its build directory.
        compiler = Path(COMPILER) if COMPILER else ROOT / "pystachy.py"
        if not (compiler.parent / "runtime.c").is_file():
            self.skipTest("the compiler is not beside its runtime")
        command = ["./" + compiler.name] if COMPILER else [sys.executable, "-B", "./pystachy.py"]
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env["PYSTACHY_LLVM"] = missing
        result = subprocess.run(command + ["doctor"], cwd=compiler.parent, env=env, capture_output=True,
                                text=True, timeout=600)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"Runtime cache: {os.path.realpath(compiler.parent)}/build", result.stdout.splitlines())

    def test_a_file_named_like_help_is_still_compiled(self):
        (self.root / "--help").write_text("print(1)\n")
        result = self.pystachy("check", "--help")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_misuse_names_the_problem_then_prints_usage_to_stderr(self):
        for args, first in (([], "usage: pystachy run FILE.py"),
                            (["frob", "g.py"], "pystachy: error: unknown command 'frob'"),
                            (["frob"], "pystachy: error: unknown command 'frob'"),
                            (["build"], "pystachy build: error: missing the source file"),
                            (["check", "--semantic"], "pystachy check: error: missing the source file")):
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

    def test_semantic_check_compiles_without_llvm_and_plain_check_only_parses(self):
        (self.root / "a.py").write_text("async def f() -> int:\n    return 1\n\n\nprint(f)\n")
        plain = self.pystachy("check", "a.py", llvm=str(self.root / "no LLVM"))
        self.assertEqual((plain.returncode, plain.stdout, plain.stderr), (0, "", ""))
        for args in (["check", "a.py", "--semantic"], ["check", "--semantic", "a.py"]):
            with self.subTest(args=args):
                result = self.pystachy(*args, llvm=str(self.root / "no LLVM"))
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertEqual(result.stderr, "a.py:1: error: async functions are not supported\n")
        result = self.pystachy("check", "g.py", "--semantic", "-O3", llvm=str(self.root / "no LLVM"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(result.stderr, "pystachy check: warning: ignoring argument '-O3'\n")
        self.assertFalse((self.root / "cache").exists())
        (self.root / "--semantic").write_text("print(1)\n")  # a file of that name is still the one checked
        result = self.pystachy("check", "--semantic", "a.py")
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(result.stderr, "pystachy check: warning: ignoring argument 'a.py'\n")

    def test_semantic_check_reports_the_rejection_corpus_as_ir_does(self):
        # A spread of tests/errors cases (not those that need an import path or compile as runtime.py)
        cases = sorted(p for p in (ROOT / "tests/errors").glob("*/*.py")
                       if not p.with_suffix(".path").exists() and not p.name.startswith("rtmode_"))
        for case in cases[:: max(1, len(cases) // 8)]:
            with self.subTest(case=case.name):
                ir = self.pystachy("ir", str(case))
                check = self.pystachy("check", str(case), "--semantic")
                self.assertEqual(ir.returncode, 1, ir.stderr)
                self.assertEqual((check.returncode, check.stdout, check.stderr), (1, "", ir.stderr))

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

    def test_build_options_are_read_before_the_settings_they_replace(self):
        # Without LLVM the build fails later, but never on the environment's tier, and the options
        # are not reported as unused.
        result = self.pystachy("build", "g.py", "-O1", "-g", "-o", "exe", llvm=str(self.root / "no LLVM"),
                               extra={"PYSTACHY_AOT_OPT": "9"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("PYSTACHY_AOT_OPT must be", result.stderr)
        self.assertNotIn("warning", result.stderr)
        result = self.pystachy("build", "g.py", "-o", "exe", llvm=str(self.root / "no LLVM"),
                               extra={"PYSTACHY_AOT_OPT": "9"})
        self.assertEqual(result.stderr, "g.py:0: error: PYSTACHY_AOT_OPT must be 0, 1 or 2\n")

    @unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to build programs")
    def test_build_options_match_their_settings(self):
        def build(output, *args, extra=None):
            result = self.pystachy("build", "g.py", "-o", output, *args, llvm=LLVM, extra=extra)
            self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
            run = subprocess.run([str(self.root / output), "x"], capture_output=True, text=True, timeout=60)
            self.assertEqual((run.returncode, run.stdout), (0, "['x']\n"))
            return result.stderr, (self.root / output).read_bytes()

        _, default = build("default")
        self.assertEqual(build("o0", "-O0")[1], build("o0env", extra={"PYSTACHY_AOT_OPT": "0"})[1])
        self.assertNotEqual(build("o0", "-O0")[1], default)
        self.assertEqual(build("o1", "-O1", extra={"PYSTACHY_AOT_OPT": "0"})[1],
                         build("o1env", extra={"PYSTACHY_AOT_OPT": "1"})[1])
        self.assertIn(b".debug_line", build("lines", "-g")[1])
        self.assertNotIn(b".debug_line", default)
        warned, _ = build("o3", "-O3")
        self.assertEqual(warned, "pystachy build: warning: ignoring argument '-O3'\n")
        build("-g")  # -o's value, not the option
        self.assertTrue((self.root / "-g").is_file())

    @unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to run programs")
    def test_run_passes_every_later_argument_to_the_program(self):
        result = self.pystachy("run", "g.py", "-O3", "--help", "-o", "x", llvm=LLVM)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, "['-O3', '--help', '-o', 'x']\n")


if __name__ == "__main__":
    unittest.main()
