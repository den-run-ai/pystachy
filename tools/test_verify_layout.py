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
        for name in ("tests/corpus.sh", "tests/run.sh", "tests/record.sh", "tests/verify.sh"):
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
if mode == "run":
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

    def test_missing_closure_helper_fails_before_compilation(self):
        self.write("tests/programs/language/closure_paths.py", "print(1)\n")
        self.write("tests/programs/language/closure_paths.out", "1\n[exit 0]\n")
        self.write("tests/programs/language/closure_paths.path", "tests/missing\n")
        result = self.run_script("tests/run.sh", "true", "jit aot",
                                 "tests/programs/language/closure_paths.py", PYSTACHY_JOBS="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("cannot prepare bracket-path fixture", result.stdout)
        self.assertIn("0 passed, 1 failed", result.stdout)

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
