"""Retained bootstrap witnesses and program-only AOT optimization controls.

The default suite needs no LLVM. Set PYSTACHY_TEST_LLVM to a matching toolchain
directory to exercise real builds, links, failure and exact IR witnesses. The
default producer is hosted; PYSTACHY_TEST_COMPILER selects a native executable.
"""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import driver

ROOT = Path(__file__).resolve().parents[1]


class RetainedWitness(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pystachy witness ' $ ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source.py"
        self.source.write_text("print(42)\n")
        self.output = self.root / "executable"
        self.output.write_bytes(b"previous executable")
        self.witness = self.root / "witness.ll"

    def args(self, *extra):
        return ["-o", str(self.output), "--emit-ir", str(self.witness), *extra]

    def reject(self, cmd, args):
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            driver.retained_ir_path(cmd, str(self.source), args)
        self.assertIn("--emit-ir", error.getvalue())

    def test_source_and_executable_aliases_reject_without_writes(self):
        for target in (self.source, self.output):
            for kind in ("path", "symlink", "hardlink"):
                with self.subTest(target=target.name, kind=kind):
                    alias = self.root / "alias"
                    if kind == "symlink":
                        alias.symlink_to(target)
                    elif kind == "hardlink":
                        alias.hardlink_to(target)
                    else:
                        alias = target
                    self.reject("build", ["-o", str(self.output), "--emit-ir", str(alias)])
                    if kind != "path":
                        alias.unlink()
        self.assertEqual(self.source.read_text(), "print(42)\n")
        self.assertEqual(self.output.read_bytes(), b"previous executable")

    def test_default_executable_alias_and_invalid_arguments(self):
        self.reject("build", ["--emit-ir", str(self.source.with_suffix(""))])
        self.reject("build", ["--emit-ir", str(self.root)])
        for args in (["--emit-ir"], ["--emit-ir", ""], ["--emit-ir", "-o", "x"],
                     self.args("--emit-ir", "another.ll")):
            with self.subTest(args=args):
                self.reject("build", args)
        for cmd in ("ir", "rt", "check", "ext"):
            with self.subTest(cmd=cmd):
                self.reject(cmd, self.args())

    def test_run_arguments_and_no_option_are_unchanged(self):
        self.assertEqual(driver.retained_ir_path("run", str(self.source), ["--emit-ir"]), "")
        self.assertEqual(driver.retained_ir_path("build", str(self.source), ["-o", "--emit-ir"]), "")
        self.assertEqual(driver.retained_ir_path("ir", str(self.source), ["-o", "output"]), "")
        self.assertEqual(driver.retained_ir_path("build", str(self.source), self.args()), str(self.witness))

    def test_alias_is_rejected_before_frontend_execution(self):
        args = [str(ROOT / "pystachy.py"), "build", str(self.source), "--emit-ir", str(self.source)]
        with patch.object(sys, "argv", args), patch.object(driver, "compile_program") as compile_program:
            with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                driver.main()
        compile_program.assert_not_called()

    def test_publication_preserves_exact_bytes_and_replaces_complete_file(self):
        self.witness.write_text("previous witness")
        ir = "; raw witness\n@x = constant i8 255\n"
        driver.publish_retained_ir(str(self.witness), str(self.source), str(self.output), ir, "unique")
        self.assertEqual(self.witness.read_bytes(), ir.encode())
        self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_publication_failure_preserves_previous_witness_and_cleans_staging(self):
        self.witness.write_text("previous witness")
        with patch.object(os, "replace", side_effect=OSError("injected rename failure")), self.assertRaises(OSError):
            driver.publish_retained_ir(str(self.witness), str(self.source), str(self.output), "new witness", "unique")
        self.assertEqual(self.witness.read_text(), "previous witness")
        self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_publication_rechecks_aliases(self):
        self.witness.symlink_to(self.source)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            driver.publish_retained_ir(str(self.witness), str(self.source), str(self.output), "new witness", "unique")
        self.assertEqual(self.source.read_text(), "print(42)\n")
        self.assertEqual(list(self.root.glob("*.tmp.*")), [])


class OptimizationTier(unittest.TestCase):
    def test_default_and_explicit_tiers(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(driver.aot_optimization(), "2")
        for tier in ("0", "1", "2"):
            with self.subTest(tier=tier), patch.dict(os.environ, PYSTACHY_AOT_OPT=tier):
                self.assertEqual(driver.aot_optimization(), tier)

    def test_invalid_tiers_fail(self):
        for tier in ("", "3", "-1", "01", "O1", " 1", "1\n", "２"):
            with self.subTest(tier=tier), patch.dict(os.environ, PYSTACHY_AOT_OPT=tier):
                with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
                    driver.aot_optimization()
                self.assertIn("PYSTACHY_AOT_OPT", error.getvalue())


@unittest.skipUnless(os.environ.get("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for real LLVM build checks")
class RealBuilds(unittest.TestCase):
    def test_tiers_preserve_raw_ir_and_failed_build_does_not_publish(self):
        with tempfile.TemporaryDirectory(prefix="pystachy real witness ") as directory:
            root = Path(directory)
            source = root / "probe.py"
            source.write_text("class Cell:\n    def __init__(self, n: int):\n        self.n = n\n\n"
                              "def numbers():\n    yield 2\n    yield 4\n\n"
                              "try:\n    print(Cell(42).n, sum(numbers()))\n    raise ValueError('ok')\n"
                              "except ValueError as error:\n    print(str(error))\n")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment.update(PYSTACHY_LLVM=os.environ["PYSTACHY_TEST_LLVM"],
                               PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(root / "cache"))
            native = os.environ.get("PYSTACHY_TEST_COMPILER")
            command = [native] if native else [sys.executable, str(ROOT / "pystachy.py")]
            expected = subprocess.run([*command, "ir", str(source)], cwd=ROOT, env=environment,
                                      capture_output=True, check=True).stdout
            self.assertNotIn(b"@pys_plain =", expected)
            for tier in ("0", "1", "2"):
                for partitions in ("0", "2"):
                    with self.subTest(tier=tier, partitions=partitions):
                        output = root / f"program-{tier}-{partitions}"
                        witness = output.with_suffix(".ll")
                        env = dict(environment, PYSTACHY_AOT_OPT=tier, PYSTACHY_BUILD_JOBS="2",
                                   PYSTACHY_LTO_PARTITIONS=partitions)
                        result = subprocess.run([*command, "build", str(source), "-o", str(output),
                                                 "--emit-ir", str(witness)], cwd=ROOT, env=env,
                                                capture_output=True, timeout=120)
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(witness.read_bytes(), expected)
                        self.assertEqual(subprocess.check_output([str(output)]), b"42 6\nok\n")
            witness = root / "failed.ll"
            witness.write_bytes(b"previous witness")
            env = dict(environment, PYSTACHY_CFLAGS="-Wl,--pystachy-deliberate-invalid-link-option")
            result = subprocess.run([*command, "build", str(source), "-o", str(root / "failed"),
                                     "--emit-ir", str(witness)], cwd=ROOT, env=env,
                                    capture_output=True, timeout=120)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(witness.read_bytes(), b"previous witness")
            self.assertEqual(list(root.glob("*.tmp.*")), [])


if __name__ == "__main__":
    unittest.main()
