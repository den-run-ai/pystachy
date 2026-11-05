"""Black-box controls for irsame's diagnostic, exit-status and IR oracle."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
MESSAGE = ("{lib}csv.py:867: error: 'Sink' object has no method 'write' "
           "(compiling csv.Writer._end(bool) for the call at {lib}csv.py:890; "
           "compiling csv.Writer.writerow(list[str]) for the call at case.py:12)\n")
COMPILER = '''import json
import os
from pathlib import Path
import sys

if len(sys.argv) == 1:
    print("usage: pystachy rt PROGRAM")
    sys.exit(2)
home = os.getenv("PYSTACHY_HOME", "")
if not home:
    home = os.path.dirname(sys.argv[0]) or "."
    if not os.path.exists(home + "/runtime.c"):
        home += "/.."
prefix = home + "/lib/"
if prefix.startswith("./"):
    prefix = prefix[2:]
settings = json.loads(Path(__file__).with_name("behavior.json").read_text())
sys.stderr.write(settings["message"].replace("{lib}", prefix))
if settings["ir"] is not None and "-o" in sys.argv:
    Path(sys.argv[sys.argv.index("-o") + 1]).write_text(settings["ir"])
sys.exit(settings["status"])
'''


class IrsameTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "tools").mkdir()
        shutil.copy2(ROOT / "tools/irsame.sh", self.root / "tools/irsame.sh")
        (self.root / "case.py").write_text("pass\n")
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("PYSTACHY_")}
        self.env.update(LC_ALL="C", PYSTACHY_JOBS="2")
        for name in ("old", "new"):
            self.home(name)
            self.compiler(name + "/pystachy")

    def home(self, name):
        path = self.root / name
        (path / "lib").mkdir(parents=True, exist_ok=True)
        (path / "runtime.c").write_text("")
        (path / "lib/csv.py").write_text("# distinct library inputs stay in place\n")

    def compiler(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!{sys.executable}\n" + COMPILER)
        path.chmod(0o755)
        self.configure(str(path.parent.relative_to(self.root)))

    def configure(self, name, message=MESSAGE, status=1, ir=None):
        (self.root / name / "behavior.json").write_text(json.dumps(
            {"message": message, "status": status, "ir": ir}))

    def compare(self, old="old/pystachy", new="new/pystachy", check=False, env=None, cases=("case.py",)):
        return subprocess.run(
            ["sh", "tools/irsame.sh", *(["--check"] if check else []), old, new, *cases],
            cwd=self.root, env=self.env if env is None else env, capture_output=True,
            text=True, timeout=20)

    def assert_identical(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "1 programs identical\n")
        self.assertEqual(result.stderr, "")

    def test_normalizes_only_compiler_library_locations_including_call_contexts(self):
        self.assert_identical(self.compare())
        self.assert_identical(self.compare(check=True))

    def test_hosted_commands_and_absolute_or_dot_prefixed_compiler_paths(self):
        self.compiler("old/pystachy.py")
        self.assert_identical(self.compare(f"{sys.executable} -B old/pystachy.py",
                                           str(self.root / "new/pystachy")))
        self.assert_identical(self.compare("./old/pystachy", "./new/pystachy"))

    def test_other_structured_contexts_and_function_descriptions(self):
        message = ("case.py:2: error: cannot use <function f ({lib}csv.py:3)> "
                   "(compiling f() for the type of 'field' at {lib}csv.py:4; "
                   "specializing C(int) for the call at {lib}csv.py:5; "
                   "making a Callable of int at {lib}csv.py:6)\n")
        for name in ("old", "new"):
            self.configure(name, message=message)
        self.assert_identical(self.compare())

    def test_compilers_in_build_use_the_parent_home(self):
        self.compiler("old/build/pystachy")
        self.assert_identical(self.compare("old/build/pystachy"))

    def test_library_prefix_is_literal_even_with_regexp_metacharacters(self):
        name = "ref[1].+|&"
        self.home(name)
        self.compiler(name + "/pystachy")
        self.assert_identical(self.compare(name + "/pystachy"))

    def test_inherited_home_overrides_compiler_adjacent_library(self):
        self.home("chosen home[1]")
        env = dict(self.env, PYSTACHY_HOME=str(self.root / "chosen home[1]"))
        # Observe canonicalized locations in a real difference, not just equal raw messages.
        self.configure("new", message=MESSAGE.replace("no method", "no attribute"))
        result = self.compare(env=env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("lib/csv.py:867: error:", result.stdout)
        self.assertNotIn("chosen home", result.stdout)
        self.configure("old", message=MESSAGE.replace("{lib}", "old/lib/"))
        self.configure("new", message=MESSAGE.replace("{lib}", "lib/"))
        self.assertEqual(self.compare(env=env).returncode, 1)

    def test_unknown_wrappers_are_not_guessed(self):
        result = self.compare("env old/pystachy", "env new/pystachy")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("old/lib/csv.py", result.stdout)
        self.assertIn("new/lib/csv.py", result.stdout)

    def test_diagnostic_text_line_numbers_and_module_names_remain_significant(self):
        for message in (MESSAGE.replace("no method", "no attribute"),
                        MESSAGE.replace(":867:", ":868:"),
                        MESSAGE.replace(":890;", ":891;"),
                        MESSAGE.replace("csv.py", "other.py")):
            with self.subTest(message=message):
                self.configure("new", message=message)
                result = self.compare()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("  messages:\n", result.stdout)

    def test_quoted_paths_and_unrelated_module_paths_remain_significant(self):
        for message in ("case.py:2: error: unsupported literal '{lib}csv.py:867'\n",
                        "case.py:2: error: unsupported literal ' at {lib}csv.py:867)'\n",
                        "case.py:2: error: unsupported literal ' ({lib}csv.py:867)'\n",
                        "other/{lib}csv.py:867: error: same message\n",
                        "case.py:2: error: cannot open {lib}csv.py\n"):
            with self.subTest(message=message):
                for name in ("old", "new"):
                    self.configure(name, message=message)
                result = self.compare()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("  messages:\n", result.stdout)

    def test_quoted_values_cannot_imitate_structured_contexts(self):
        contexts = ("(compiling f() at {lib}csv.py:867)",
                    "(specializing C(int) for the call at {lib}csv.py:867)",
                    "(making a Callable of int at {lib}csv.py:867)",
                    "<function f ({lib}csv.py:867)>")
        for context in contexts:
            for quote in ("'", '"'):
                for suffix in ("", " (compiling real() for the call at {lib}csv.py:890)"):
                    with self.subTest(context=context, quote=quote, suffix=suffix):
                        message = f"case.py:2: error: unsupported literal {quote}{context}{quote}{suffix}\n"
                        for name in ("old", "new"):
                            self.configure(name, message=message)
                        result = self.compare()
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertIn("  messages:\n", result.stdout)

    def test_escaped_quotes_and_ambiguous_apostrophes_stay_conservative(self):
        for message in ("case.py:2: error: unsupported literal 'a\\' (compiling f() at {lib}csv.py:8)'\n",
                        'case.py:2: error: unsupported literal "a\\" <function f ({lib}csv.py:8)>"\n',
                        "case.py:2: error: Pystachy's literal '(compiling f() at {lib}csv.py:8)'\n"):
            with self.subTest(message=message):
                for name in ("old", "new"):
                    self.configure(name, message=message)
                result = self.compare()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("  messages:\n", result.stdout)

    def test_status_is_compared_after_path_only_message_differences(self):
        self.configure("new", status=2)
        result = self.compare()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("  exit status 1 -> 2\n", result.stdout)
        self.assertNotIn("  messages:\n", result.stdout)

    def test_ir_differences_and_missing_output_are_not_normalized(self):
        self.configure("old", status=0, ir="; old/lib/csv.py\n")
        for ir in ("; new/lib/csv.py\n", None):
            with self.subTest(ir=ir):
                self.configure("new", status=0, ir=ir)
                result = self.compare()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("  IR", result.stdout)
                self.assertNotIn("  messages:\n", result.stdout)

    def test_times_append_every_completed_case_without_changing_the_verdict(self):
        cases = ("third.py", "case.py", "second.py")
        for case in cases:
            (self.root / case).write_text("pass\n")
        times = self.root / "times.log"
        env = dict(self.env, PYSTACHY_CASE_TIMES=str(times))
        for differs in (False, True):
            self.configure("new", status=2 if differs else 1)
            result = self.compare(env=env, cases=cases)
            self.assertEqual(result.returncode, int(differs), result.stdout + result.stderr)
        rows = [line.split(" ", 1) for line in times.read_text().splitlines()]
        self.assertCountEqual([case for _, case in rows[:3]], cases)
        self.assertCountEqual([case for _, case in rows[3:]], cases)
        self.assertTrue(all(ms.isascii() and ms.isdigit() for ms, _ in rows))
        # --check has the same optional timing interface.
        self.configure("new")
        self.assert_identical(self.compare(check=True, env=env))
        self.assertEqual(times.read_text().splitlines()[-1].split(" ", 1)[1], "case.py")

    def test_completed_times_survive_interruption_of_a_later_case(self):
        (self.root / "blocked.py").write_text("pass\n")
        wrapper = self.root / "slow"
        wrapper.write_text("#!/bin/sh\nif [ \"$2\" = blocked.py ]; then sleep 30; fi\nexec new/pystachy \"$@\"\n")
        wrapper.chmod(0o755)
        for name in ("old", "new"):
            self.configure(name, message="", status=0, ir="; same\n")
        times = self.root / "times.log"
        process = subprocess.Popen(
            ["sh", "tools/irsame.sh", "old/pystachy", "./slow", "case.py", "blocked.py"],
            cwd=self.root, env=dict(self.env, PYSTACHY_CASE_TIMES=str(times)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            while (not times.exists() or not times.read_text()) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(times.exists(), "the completed case must be recorded before all workers finish")
            self.assertEqual(times.read_text().splitlines()[0].split(" ", 1)[1], "case.py")
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=5)
        self.assertEqual(len(times.read_text().splitlines()), 1)

    def test_timing_is_optional_and_a_non_gnu_date_preserves_the_oracle(self):
        times = self.root / "times.log"
        self.assert_identical(self.compare())
        self.assertFalse(times.exists())
        binary = self.root / "bin"
        binary.mkdir()
        date = binary / "date"
        date.write_text("#!/bin/sh\necho 1700000000N\n")
        date.chmod(0o755)
        env = dict(self.env, PATH=str(binary) + os.pathsep + self.env["PATH"],
                   PYSTACHY_CASE_TIMES=str(times))
        result = self.compare(env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "1 programs identical\n")
        self.assertIn("PYSTACHY_CASE_TIMES needs date +%s%N", result.stderr)
        self.assertFalse(times.exists())


if __name__ == "__main__":
    unittest.main()
