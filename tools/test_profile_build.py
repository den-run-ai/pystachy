"""Profile-guided builds reach only the whole-program step and the link.

The ordinary controls need no LLVM. Set PYSTACHY_TEST_LLVM to a toolchain with llvm-profdata to
run the real generate, merge and use round; it checks the programs' output, not their speed.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import driver

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = (
    "print(42)\n",
    "class Cell:\n    def __init__(self, n: int):\n        self.n = n\n"
    "def values():\n    yield Cell(42).n\n    yield 7\n"
    "total = 0\nfor i in range(2000):\n    total += sum(values()) if i % 3 else i\nprint(total)\n",
)
STUB = '''import json
from src.pystachy_compiler import driver
def command(name, text):
    print(json.dumps([name, text]))
    return 0
driver.timed_sh = command
driver.runtime_ir = lambda *args: "; runtime\\n"
driver.main()
'''


def environment(directory):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(directory / "cache"),
               PYSTACHY_LLVM=str(directory / "missing-tools"), PYSTACHY_JOBS="2")
    return env


class ProfileControls(unittest.TestCase):
    def rejected(self, settings, message):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "probe.py"
            source.write_text("print(42)\n")
            args = [str(ROOT / "pystachy.py"), "build", str(source)]
            clean = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_PROFILE_")}
            with patch.object(sys, "argv", args), patch.dict(os.environ, clean | settings, clear=True):
                with patch.object(driver, "compile_program") as frontend:
                    with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit):
                        driver.main()
                    frontend.assert_not_called()
            self.assertIn(message, stderr.getvalue())

    def test_both_settings_fail_before_the_frontend(self):
        self.rejected({"PYSTACHY_PROFILE_GENERATE": "raw", "PYSTACHY_PROFILE_USE": "merged.profdata"},
                      "PYSTACHY_PROFILE_GENERATE and PYSTACHY_PROFILE_USE cannot both be set")

    def test_a_missing_profile_fails_before_the_frontend(self):
        with tempfile.TemporaryDirectory() as temporary:
            for missing in (str(Path(temporary) / "none.profdata"), temporary):
                with self.subTest(missing=missing):
                    self.rejected({"PYSTACHY_PROFILE_USE": missing}, "PYSTACHY_PROFILE_USE: no profile at " + missing)

    def test_flags_reach_the_optimizing_step_and_the_link_only(self):
        # The actual frontend, branch selection and command construction; only native execution is
        # stubbed, as in test_bootstrap_tier.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "probe.py"
            profile = root / "it's merged.profdata"  # (a name the shell must not split or expand)
            profile.write_bytes(b"")
            raw = str(root / "raw profiles")
            for program_index, program in enumerate(PROGRAMS):
                source.write_text(program)
                optimizer = "program.optimize_codegen" if program_index == 0 else "program.llvm_optimize"
                for setting, flag, linked in ((None, None, False),
                                              ({"PYSTACHY_PROFILE_GENERATE": raw}, "-fprofile-generate=" + raw, True),
                                              ({"PYSTACHY_PROFILE_USE": str(profile)}, "-fprofile-use=" + str(profile), False)):
                    with self.subTest(program=program_index, setting=setting):
                        result = subprocess.run([sys.executable, "-c", STUB, "build", str(source),
                                                 "-o", str(root / "program")], cwd=ROOT,
                                                env=environment(root) | (setting or {}),
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        calls = dict(json.loads(line) for line in result.stdout.splitlines())
                        with_flag = {name for name, text in calls.items()
                                     if any(word.startswith("-fprofile") for word in shlex.split(text))}
                        expected = set() if flag is None else {optimizer} | ({"program.link"} if linked else set())
                        self.assertEqual(with_flag, expected)
                        for name in expected:
                            words = shlex.split(calls[name])
                            self.assertEqual([word for word in words if word.startswith("-fprofile")], [flag])
                        if program_index:
                            self.assertIn("program.codegen", calls)

    def test_other_commands_ignore_the_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "probe.py"
            source.write_text(PROGRAMS[1])
            both = {"PYSTACHY_PROFILE_GENERATE": "raw", "PYSTACHY_PROFILE_USE": str(root / "none.profdata")}
            for mode in ("ir", "check"):
                command = [sys.executable, str(ROOT / "pystachy.py"), mode, str(source)]
                ordinary = subprocess.run(command, cwd=ROOT, env=environment(root), capture_output=True, timeout=30)
                changed = subprocess.run(command, cwd=ROOT, env=environment(root) | both, capture_output=True, timeout=30)
                self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
                self.assertEqual((changed.returncode, changed.stdout, changed.stderr),
                                 (ordinary.returncode, ordinary.stdout, ordinary.stderr))

    def test_verification_removes_inherited_profile_settings(self):
        # Run the production sanitization shell, without starting verification.
        source = (ROOT / "tests/verify.sh").read_text()
        start = source.index("ign=$(env |")
        stop = source.index("\nLLVM=", start)
        script = ('set -e\n' + source[start:stop] + '\ntest "${PYSTACHY_PROFILE_GENERATE+x}" != x\n'
                  'test "${PYSTACHY_PROFILE_USE+x}" != x\nprintf "%s\\n" "$ign"\n')
        result = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=10,
                                env=os.environ | {"PYSTACHY_PROFILE_GENERATE": "raw", "PYSTACHY_PROFILE_USE": "x"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PYSTACHY_PROFILE_GENERATE", result.stdout)
        self.assertIn("PYSTACHY_PROFILE_USE", result.stdout)


@unittest.skipUnless(os.environ.get("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM to exercise real profiles")
class RealProfiles(unittest.TestCase):
    def test_generate_merge_and_use_keep_the_output(self):
        llvm = Path(os.environ["PYSTACHY_TEST_LLVM"])
        profdata = llvm / "llvm-profdata"
        if not profdata.exists():
            self.skipTest("no llvm-profdata beside the toolchain's clang")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = environment(root) | {"PYSTACHY_LLVM": str(llvm)}
            native = os.environ.get("PYSTACHY_TEST_COMPILER")
            compiler = [native] if native else [sys.executable, str(ROOT / "pystachy.py")]
            for index, program in enumerate(PROGRAMS):
                with self.subTest(program=index):
                    source = root / f"source_{index}.py"
                    source.write_text(program)
                    oracle = subprocess.run([sys.executable, str(source)], env=env,
                                            capture_output=True, check=True, timeout=10)
                    raw, merged = root / f"raw {index}", root / f"merged_{index}.profdata"
                    plain, generating, using = (root / f"{name}_{index}" for name in ("plain", "generating", "using"))
                    for output, setting in ((plain, {}), (generating, {"PYSTACHY_PROFILE_GENERATE": str(raw)})):
                        built = subprocess.run(compiler + ["build", str(source), "-o", str(output)], cwd=ROOT,
                                               env=env | setting, capture_output=True, timeout=180)
                        self.assertEqual(built.returncode, 0, built.stderr)
                    self.assertFalse(raw.exists())  # (written by a run, not by the build)
                    for _ in range(2):
                        ran = subprocess.run([str(generating)], env=env, capture_output=True, timeout=30)
                        self.assertEqual((ran.returncode, ran.stdout, ran.stderr),
                                         (oracle.returncode, oracle.stdout, oracle.stderr))
                    profiles = sorted(raw.glob("*.profraw"))
                    self.assertTrue(profiles)
                    subprocess.run([str(profdata), "merge", "-o", str(merged)] + [str(p) for p in profiles],
                                   check=True, capture_output=True, timeout=30)
                    built = subprocess.run(compiler + ["build", str(source), "-o", str(using)], cwd=ROOT,
                                           env=env | {"PYSTACHY_PROFILE_USE": str(merged)},
                                           capture_output=True, timeout=180)
                    self.assertEqual(built.returncode, 0, built.stderr)
                    self.assertNotIn(b"warning", built.stderr)
                    for output in (plain, using):
                        for stress in (False, True):
                            actual = subprocess.run([str(output)], capture_output=True, timeout=30,
                                                    env=env | ({"PYSTACHY_GC_STRESS": "1"} if stress else {}))
                            self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                             (oracle.returncode, oracle.stdout, oracle.stderr))
                    self.assertEqual(sorted(raw.glob("*.profraw")), profiles)  # (the using build writes none)


if __name__ == "__main__":
    unittest.main()
