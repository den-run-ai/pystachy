"""The corpus's layout (tests/corpus.sh): which files are cases, and that a test left outside the areas,
or two cases of one name, fail tests/run.sh, tests/verify.sh and tests/record.sh --check instead of
being skipped."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests/corpus.sh", "tests/run.sh", "tests/record.sh", "tests/verify.sh",
                     "tests/prepare_path.sh", "tools/irsame.sh", "tools/check_ir.sh"):
            self.write(name, (ROOT / name).read_text())
        # a case of each suite, helper packages and other suites' files, which are no cases
        self.write("tests/programs/b/two.py", "print(2)\n")
        self.write("tests/programs/b/two.out", "2\n[exit 0]\n")
        self.write("tests/programs/a/one.py", "print(1)\n")
        self.write("tests/programs/a/one.out", "1\n[exit 0]\n")
        self.write("tests/deviations/dev.py", "print(3)\n")
        self.write("tests/errors/a/rej.py", "# error: no\n")
        self.write("tests/mods/__init__.py", "")
        self.write("tests/emods/helper.py", "")
        self.write("tests/ir/probe.py", "")
        self.write("tests/programs/a/__pycache__/one.cpython-313.pyc", "")

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def sh(self, script):
        return subprocess.run(["sh", "-c", ". tests/corpus.sh; " + script], cwd=self.root, text=True,
                              capture_output=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, check=True).stdout

    def run_script(self, *args, **env):
        return subprocess.run(["sh", *args], cwd=self.root, text=True, capture_output=True, timeout=60,
                              env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", **env})

    def test_cases_are_the_areas_programs_the_deviations_and_the_areas_rejections(self):
        self.assertEqual(self.sh("corpus").split(), ["tests/programs/a/one.py", "tests/programs/b/two.py",
                                                     "tests/deviations/dev.py", "tests/errors/a/rej.py"])
        self.assertEqual(self.sh("corpus_strays"), "")

    def test_a_test_outside_the_areas_is_a_stray(self):
        strays = ["tests/old.py", "tests/old.out", "tests/old.path", "tests/errors/old.py", "tests/errors/old.path",
                  "tests/errors/rej.out", "tests/programs/old.py", "tests/programs/a/sub/deep.py",
                  "tests/errors/a/sub/deep.py"]
        for name in strays:
            self.write(name, "")
        self.assertEqual(sorted(self.sh("corpus_strays").split()), sorted(strays))
        self.assertNotIn("tests/old.py", self.sh("corpus"))

    def test_run_refuses_a_stray_and_a_test_named_in_the_old_layout(self):
        self.write("tests/old.py", "print(0)\n")
        result = self.run_script("tests/run.sh", "./no-compiler")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("tests/old.py", result.stderr)
        result = self.run_script("tests/run.sh", "./no-compiler", "jit", "tests/old.py")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("not a test: tests/old.py", result.stderr)

    def test_verify_refuses_a_stray(self):
        self.write("tests/errors/old.py", "# error: no\n")
        result = self.run_script("tests/verify.sh", "bootstrap")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("tests/errors/old.py", result.stderr)

    def test_closure_helper_uses_a_temporary_bracket_path_in_both_modes(self):
        for name in ("tests/programs/language/closure_paths.py",
                     "tests/programs/language/closure_paths.path",
                     "tests/closure_path_modules/closure_path_fixture.py"):
            self.write(name, (ROOT / name).read_text())
        self.write("tests/programs/language/closure_paths.out", "ok\n[exit 0]\n")
        self.write("compiler", f"#!{sys.executable}\n" + '''import os
from pathlib import Path
import sys

if len(sys.argv) < 3:
    sys.exit(0)
mode, source = sys.argv[1:3]
if Path(source).name == "warm.py":
    sys.exit(0)
helper = Path(os.environ["PYSTACHY_PATH"])
assert helper.name == "paths]"
assert not helper.is_relative_to(Path.cwd())
assert (helper / "closure_path_fixture.py").read_bytes() == Path(
    "tests/closure_path_modules/closure_path_fixture.py").read_bytes()
with open("calls", "a") as log:
    log.write(mode + " " + str(helper) + "\\n")
if mode == "ir":
    Path(sys.argv[sys.argv.index("-o") + 1]).write_text("; test IR\\n")
elif mode == "run":
    print("ok")
else:
    output = Path(sys.argv[sys.argv.index("-o") + 1])
    output.write_text("#!/bin/sh\\nprintf 'ok\\\\n'\\n")
    output.chmod(0o755)
''')
        (self.root / "compiler").chmod(0o755)
        result = self.run_script("tests/run.sh", "./compiler", "jit aot",
                                 "tests/programs/language/closure_paths.py", PYSTACHY_JOBS="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 passed, 0 failed", result.stdout)
        calls = (self.root / "calls").read_text().splitlines()
        self.assertEqual([call.split(" ", 1)[0] for call in calls], ["run", "build"])
        for call in calls:
            self.assertFalse(Path(call.split(" ", 1)[1]).exists())
        self.assertFalse((self.root / "tests/paths]").exists())

        self.write("bin/llvm-as", "#!/bin/sh\ncat > /dev/null\n")
        (self.root / "bin/llvm-as").chmod(0o755)
        for command in (("tools/irsame.sh", "./compiler", "./compiler"),
                        ("tools/check_ir.sh", "./compiler")):
            with self.subTest(command=command):
                (self.root / "calls").unlink()
                result = self.run_script(*command, "tests/programs/language/closure_paths.py",
                                         PYSTACHY_JOBS="1", PYSTACHY_LLVM=str(self.root / "bin"))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                calls = (self.root / "calls").read_text().splitlines()
                self.assertEqual(len(calls), 2 if "irsame" in command[0] else 1)
                for call in calls:
                    self.assertTrue(call.startswith("ir "))
                    self.assertFalse(Path(call.split(" ", 1)[1]).exists())

    def test_missing_closure_helper_fails_before_compilation(self):
        self.write("tests/programs/language/closure_paths.py", "print(1)\n")
        self.write("tests/programs/language/closure_paths.out", "1\n[exit 0]\n")
        self.write("tests/programs/language/closure_paths.path", "tests/missing\n")
        result = self.run_script("tests/run.sh", "true", "jit aot",
                                 "tests/programs/language/closure_paths.py", PYSTACHY_JOBS="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cannot prepare bracket-path fixture", result.stdout)
        self.assertIn("0 passed, 1 failed", result.stdout)
        for command in (("tools/irsame.sh", "true", "true"), ("tools/check_ir.sh", "true")):
            with self.subTest(command=command):
                result = self.run_script(*command, "tests/programs/language/closure_paths.py",
                                         PYSTACHY_JOBS="1")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("cannot prepare import path", result.stdout)

    def test_check_recordings_fails_on_a_stray_and_on_two_cases_of_one_name(self):
        version = "%d.%d.%d" % sys.version_info[:3]
        self.write(".python-version", version + "\n")
        self.write("lib/README.md", "")
        self.write("tests/old.py", "print(0)\n")
        self.write("tests/programs/b/one.py", "print(1)\n")
        self.write("tests/programs/b/one.out", "1\n[exit 0]\n")
        result = self.run_script("tests/record.sh", "--check", PYTHON=sys.executable)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL tests/old.py: no run tests it here", result.stdout)
        self.assertIn("FAIL tests/programs/*/one.py: two cases have that name", result.stdout)
        self.assertNotIn("FAIL tests/programs/a/__pycache__", result.stdout)
        self.assertNotIn("FAIL one:", result.stdout)  # (each program's recording is CPython's)

    def test_runtime_abi_uses_bracket_path_and_fails_when_preparation_fails(self):
        for name in ("tools/rtabi.py", "tools/strabi.py", "src/__init__.py",
                     "src/pystachy_compiler/__init__.py", "src/pystachy_compiler/specs.py",
                     "src/pystachy_compiler/diagnostics.py", "src/pystachy_compiler/names.py",
                     "tests/programs/language/closure_paths.py",
                     "tests/programs/language/closure_paths.path",
                     "tests/closure_path_modules/closure_path_fixture.py"):
            self.write(name, (ROOT / name).read_text())
        self.write("runtime.py", "def pys_probe() -> int: ...\n")
        self.write("abi-compiler", f"#!{sys.executable}\n" + '''import os
from pathlib import Path
import sys
if sys.argv[1] == "rt":
    print('@s.0 = private unnamed_addr global {i64, i64, i64, [2 x i8]} {i64 1, i64 0, i64 2, [2 x i8] c"a\\\\00"}, align 8')
if sys.argv[-1].endswith("closure_paths.py"):
    helper = Path(os.environ["PYSTACHY_PATH"])
    assert helper.name == "paths]"
    assert (helper / "closure_path_fixture.py").read_bytes() == Path(
        "tests/closure_path_modules/closure_path_fixture.py").read_bytes()
    Path("observed-path").write_text(str(helper))
print("declare i64 @pys_probe()")
''')
        self.write("llvm/clang", f"#!{sys.executable}\n" +
                   'print("%struct.Str = type { i64, i64, i64, [0 x i8] }")\n'
                   'print("define i64 @pys_probe()")\n'
                   'for name, offset in [("len", 0), ("dict_hash", 8), ("chars1", 16), ("s", 24), ("size", 24)]:\n'
                   '    print(f"@pystachy_abi_str_{name} = constant i64 {offset}")\n')
        for name in ("abi-compiler", "llvm/clang"):
            (self.root / name).chmod(0o755)

        def run():
            return subprocess.run(
                [sys.executable, "tools/rtabi.py", "./abi-compiler"], cwd=self.root,
                text=True, capture_output=True, timeout=20,
                env={"PATH": "/usr/bin:/bin", "PYSTACHY_LLVM": str(self.root / "llvm")})

        result = run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 mismatches", result.stdout)
        observed = self.root / "observed-path"
        self.assertFalse(Path(observed.read_text()).exists())
        observed.unlink()
        (self.root / "tests/closure_path_modules/closure_path_fixture.py").unlink()
        result = run()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("cannot prepare bracket-path fixture", result.stderr)
        self.assertFalse(observed.exists())

    def test_record_finds_a_program_by_its_name_or_its_path(self):
        version = "%d.%d.%d" % sys.version_info[:3]
        self.write(".python-version", version + "\n")
        (self.root / "tests/programs/a/one.out").unlink()
        result = self.run_script("tests/record.sh", "one", PYTHON=sys.executable)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "tests/programs/a/one.out").read_text(), "1\n[exit 0]\n")
        result = self.run_script("tests/record.sh", "tests/programs/b/two.py", PYTHON=sys.executable)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("tests/old.py", "missing"):
            result = self.run_script("tests/record.sh", name, PYTHON=sys.executable)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
