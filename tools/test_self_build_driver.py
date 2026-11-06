"""Retained bootstrap witnesses and program-only AOT optimization controls.

The default suite needs no LLVM. Set PYSTACHY_TEST_LLVM to a matching toolchain
directory to exercise real builds, links, failure and exact IR witnesses. The
default producer is hosted; PYSTACHY_TEST_COMPILER selects a native executable.
"""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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


class InliningPolicy(unittest.TestCase):
    def test_default_and_explicit_thresholds(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(driver.aot_inline_flags(), "")
        for value, expected in (("", ""), ("0", "0"), ("75", "75"), ("00075", "75"), ("10000", "10000")):
            with self.subTest(value=value), patch.dict(os.environ, PYSTACHY_AOT_INLINE_THRESHOLD=value):
                self.assertEqual(driver.aot_inline_flags(), " -mllvm -inline-threshold=" + expected if expected else "")

    def test_invalid_policy_rejects_before_frontend_or_tool_execution(self):
        for value in ("-1", "+75", "10001", "000000", "75.0", " 75", "75\n", "７５", "75; false"):
            with self.subTest(value=value), patch.dict(os.environ, PYSTACHY_AOT_INLINE_THRESHOLD=value):
                with patch.object(sys, "argv", ["pystachy", "build", "unused.py"]), \
                     patch.object(driver, "compile_program") as frontend, patch.object(driver, "sh") as shell, \
                     contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
                    driver.main()
                self.assertIn("PYSTACHY_AOT_INLINE_THRESHOLD", error.getvalue())
                frontend.assert_not_called()
                shell.assert_not_called()

    def test_policy_is_not_parsed_for_frontend_only_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "probe.py"
            source.write_text("print(42)\n")
            with patch.dict(os.environ, PYSTACHY_AOT_INLINE_THRESHOLD="invalid"), \
                 patch.object(sys, "argv", ["pystachy", "check", str(source)]), \
                 patch.object(driver, "aot_inline_flags") as flags:
                driver.main()
            flags.assert_not_called()


class AllocatorRouting(unittest.TestCase):
    def test_runtime_declaration_selects_allocator_pipeline(self):
        from src.pystachy_compiler.specs import RTSYM
        from src.pystachy_compiler.utils import runtime_decl
        declaration = runtime_decl(RTSYM["pys_new"]) + "\n"
        for prefix in ("", "; generated by pystachy\n"):
            with self.subTest(prefix=prefix):
                self.assertTrue(driver.uses_new_allocator(prefix + declaration))

    def test_strings_comments_and_other_names_do_not_select_allocator_pipeline(self):
        for text in ('@text = constant [27 x i8] c"declare ptr @pys_new(i64)\\0A\\00"\n',
                     '; declare ptr @pys_new(i64)\n',
                     'declare ptr @pys_newer(i64)\n',
                     'declare ptr @pys_alloc(i64)\n'):
            with self.subTest(text=text):
                self.assertFalse(driver.uses_new_allocator(text))

    def test_generated_ir_distinguishes_embedded_templates_and_real_allocations(self):
        with tempfile.TemporaryDirectory(prefix="pystachy allocator routing ") as directory:
            source = Path(directory) / "probe.py"
            cases = [("print('@pys_new(')\nprint('declare ptr @pys_new(i64)\\n')\n", False),
                     ("class Cell:\n    def __init__(self, n: int):\n        self.n = n\n"
                      "items = [Cell(42)]\nprint(items[0].n)\n", True)]
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            for program, expected in cases:
                with self.subTest(allocator=expected):
                    source.write_text(program)
                    ir = subprocess.check_output([sys.executable, str(ROOT / "pystachy.py"), "ir", str(source)],
                                                 cwd=ROOT, env=environment).decode("latin-1")
                    self.assertIn("@pys_new(", ir)
                    self.assertEqual(driver.uses_new_allocator(ir), expected)


@unittest.skipUnless(os.environ.get("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for LLVM allocator checks")
class RealAllocatorRouting(unittest.TestCase):
    def test_string_marker_with_other_alwaysinline_functions_preserves_object_bytes(self):
        with tempfile.TemporaryDirectory(prefix="pystachy allocator codegen ") as directory:
            root = Path(directory)
            llvm = Path(os.environ["PYSTACHY_TEST_LLVM"])
            source = root / "input.ll"
            source.write_text('@text = constant [27 x i8] c"declare ptr @pys_new(i64)\\0A\\00"\n'
                              'define internal i64 @first(i64 %x) alwaysinline { %r = add i64 %x, 1\n ret i64 %r }\n'
                              'define internal i64 @second(i64 %x) { %r = mul i64 %x, 2\n ret i64 %r }\n'
                              'define i64 @make(i64 %x) { %a = call i64 @first(i64 %x)\n'
                              ' %b = call i64 @second(i64 %a) alwaysinline\n ret i64 %b }\n')
            self.assertFalse(driver.uses_new_allocator(source.read_text()))
            module = root / "input.bc"
            subprocess.run([str(llvm / "llvm-as"), str(source), "-o", str(module)], check=True, capture_output=True)
            for tier in ("0", "1", "2"):
                with self.subTest(tier=tier):
                    direct, optimized, late, previous = [root / name for name in ("direct.o", "optimized.bc", "late.bc", "previous.o")]
                    subprocess.run([str(llvm / "clang"), "-O" + tier, "-c", str(module), "-o", str(direct)],
                                   check=True, capture_output=True)
                    subprocess.run([str(llvm / "clang"), "-O" + tier, "-c", "-emit-llvm", str(module), "-o", str(optimized)],
                                   check=True, capture_output=True)
                    subprocess.run([str(llvm / "opt"), "-passes=forceattrs,always-inline", *driver.LATE_INLINE.split(),
                                    str(optimized), "-o", str(late)], check=True, capture_output=True)
                    subprocess.run([str(llvm / "clang"), "-O" + tier, "-c", "-Xclang", "-disable-llvm-passes",
                                    str(late), "-o", str(previous)], check=True, capture_output=True)
                    self.assertEqual(direct.read_bytes(), previous.read_bytes())


@unittest.skipUnless(os.environ.get("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for real LLVM build checks")
class RealBuilds(unittest.TestCase):
    def test_inline_policy_preserves_ir_behavior_and_runtime_cache(self):
        with tempfile.TemporaryDirectory(prefix="pystachy inline policy ") as directory:
            root = Path(directory)
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment.update(PYSTACHY_LLVM=os.environ["PYSTACHY_TEST_LLVM"], PYSTACHY_HOME=str(ROOT),
                               PYSTACHY_CACHE=str(root / "cache"), PYSTACHY_TIMING="1")
            native = os.environ.get("PYSTACHY_TEST_COMPILER")
            command = [native] if native else [sys.executable, str(ROOT / "pystachy.py")]
            # Runtime cache publication requires settled compiler/tool inputs.
            time.sleep(2.05)
            cache_entries = None
            programs = (("plain", "print(42)\n", b"42\n"),
                        ("allocated", "class Cell:\n    def __init__(self, n: int):\n        self.n = n\n"
                         "cells = [Cell(i) for i in range(100)]\n"
                         "try:\n    print(sum(c.n for c in cells))\n    raise ValueError('ok')\n"
                         "except ValueError as error:\n    print(str(error))\n", b"4950\nok\n"))
            for label, program, expected_stdout in programs:
                source = root / (label + ".py")
                source.write_text(program)
                expected_ir = subprocess.run([*command, "ir", str(source)], cwd=ROOT, env=environment,
                                             capture_output=True, check=True).stdout
                default_binary = None
                for policy, threshold in (("unset", None), ("empty", ""), ("0", "0"), ("75", "75")):
                    output = root / (label + "-" + policy)
                    witness = output.with_suffix(".ll")
                    with self.subTest(program=label, policy=policy):
                        env = dict(environment)
                        if threshold is not None:
                            env["PYSTACHY_AOT_INLINE_THRESHOLD"] = threshold
                        result = subprocess.run([*command, "build", str(source), "-o", str(output),
                                                 "--emit-ir", str(witness)], cwd=ROOT, env=env,
                                                capture_output=True, timeout=120)
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(witness.read_bytes(), expected_ir)
                        if threshold is None:
                            default_binary = output.read_bytes()
                        elif threshold == "":
                            self.assertEqual(output.read_bytes(), default_binary)
                        for stress in ("", "1"):
                            self.assertEqual(subprocess.check_output([str(output)],
                                env=dict(environment, PYSTACHY_GC_STRESS=stress), timeout=30), expected_stdout)
                        self.assertEqual(b"program.late_inline" in result.stderr, label == "allocated")
                        timings = {line.split(b"\t")[1] for line in result.stderr.splitlines()
                                   if line.startswith(b"pystachy-timing\t")}
                        self.assertIn(b"runtime.cache_lookup", timings)
                        current_cache = {}
                        for path in (root / "cache").glob("runtime-py-*"):
                            if path.is_file():
                                stat = path.stat()
                                current_cache[path.name] = (hashlib.sha256(path.read_bytes()).hexdigest(),
                                                            stat.st_ino, stat.st_mtime_ns)
                        self.assertTrue(current_cache)
                        if cache_entries is None:
                            self.assertIn(b"runtime.frontend", timings)
                            self.assertIn(b"runtime.llvm_optimize", timings)
                        else:
                            self.assertEqual(current_cache, cache_entries)
                            self.assertEqual({name for name in timings if name.startswith(b"runtime.")},
                                             {b"runtime.cache_lookup"})
                        cache_entries = current_cache

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
