"""Experimental AOT tiers preserve bootstrap scope and mandatory witnesses.

The ordinary controls need no LLVM. Set PYSTACHY_TEST_LLVM to run the optional
real-tier differential checks; they do not qualify general application parity.
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

import check_bootstrap_tier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import driver

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = (
    "print(42)\n",
    "class Cell:\n    def __init__(self, n: int):\n        self.n = n\n"
    "def values():\n    yield Cell(42).n\n    yield 7\n"
    "try:\n    print(sum(values()))\n    raise ValueError('ok')\n"
    "except ValueError as error:\n    print(str(error))\n",
)


def environment(directory):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(directory / "cache"),
               PYSTACHY_LLVM=str(directory / "missing-tools"), PYSTACHY_JOBS="2")
    return env


class TierControls(unittest.TestCase):
    def test_invalid_tiers_fail_before_the_frontend(self):
        for value in ("", "3", "-1", "01", " 1", "1;exit"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary) / "probe.py"
                source.write_text("print(42)\n")
                args = [str(ROOT / "pystachy.py"), "build", str(source)]
                with patch.object(sys, "argv", args), patch.dict(os.environ, PYSTACHY_AOT_OPT=value):
                    with patch.object(driver, "compile_program") as frontend:
                        with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit):
                            driver.main()
                        frontend.assert_not_called()
                self.assertIn("PYSTACHY_AOT_OPT must be 0, 1 or 2", stderr.getvalue())

    def test_actual_backend_selects_program_tier_without_changing_runtime_tier(self):
        # Exercise the actual frontend, branch selection and command construction;
        # stub only native execution so the controls remain cheap and deterministic.
        script = '''import json
from src.pystachy_compiler import driver
def command(name, text):
    print(json.dumps([name, text]))
    return 0
driver.timed_sh = command
driver.runtime_ir = lambda *args: "; runtime\\n"
driver.main()
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "probe.py"
            for program_index, program in enumerate(PROGRAMS):
                source.write_text(program)
                for tier, cflags in [(tier, cflags) for tier in (None, "0", "1", "2")
                                     for cflags in ("", "-O0")]:
                    with self.subTest(program=program_index, tier=tier, cflags=cflags):
                        env = environment(root)
                        if tier is not None:
                            env["PYSTACHY_AOT_OPT"] = tier
                        if cflags:
                            env["PYSTACHY_CFLAGS"] = cflags
                        result = subprocess.run([sys.executable, "-c", script, "build", str(source),
                                                 "-o", str(root / "program")], cwd=ROOT, env=env,
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        calls = dict(json.loads(line) for line in result.stdout.splitlines())
                        stages = ["program.optimize_codegen"] if program_index == 0 else [
                            "program.llvm_optimize", "program.codegen"]
                        for name in stages:
                            flags = shlex.split(calls[name])
                            self.assertEqual([flag for flag in flags if flag.startswith("-O")],
                                             ["-O" + (tier or "2")] + ([cflags] if cflags else []))
                        self.assertIn(" -O2 ", calls["runtime.c"])
                        if program_index:
                            self.assertIn("program.late_inline", calls)

    def test_raw_ir_and_parse_command_ignore_aot_only_setting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "probe.py"
            source.write_text(PROGRAMS[1])
            for mode in ("ir", "check"):
                command = [sys.executable, str(ROOT / "pystachy.py"), mode, str(source)]
                ordinary = subprocess.run(command, cwd=ROOT, env=environment(root),
                                          capture_output=True, timeout=30)
                changed = subprocess.run(command, cwd=ROOT,
                                         env=environment(root) | {"PYSTACHY_AOT_OPT": "invalid"},
                                         capture_output=True, timeout=30)
                self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
                self.assertEqual((changed.returncode, changed.stdout, changed.stderr),
                                 (ordinary.returncode, ordinary.stdout, ordinary.stderr))

    def test_verification_removes_inherited_aot_tier(self):
        # Run the production sanitization shell, without starting verification.
        source = (ROOT / "tests/verify.sh").read_text()
        start = source.index("ign=$(env |")
        stop = source.index("\nLLVM=", start)
        script = 'set -e\n' + source[start:stop] + '\ntest "${PYSTACHY_AOT_OPT+x}" != x\nprintf "%s\\n" "$ign"\n'
        result = subprocess.run(["sh", "-c", script], env=os.environ | {"PYSTACHY_AOT_OPT": "1"},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PYSTACHY_AOT_OPT", result.stdout)


class MakeBootstrapControls(unittest.TestCase):
    def test_qualification_forces_rebuild_of_a_newer_existing_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source").touch()
            (root / "pystachy").write_text("stale compiler\n")
            os.utime(root / "source", (1, 1))
            (root / "Makefile").write_text(
                'pystachy: source\n\ttest "$(BOOTSTRAP_AOT_OPT)" = 1\n'
                '\tprintf "rebuilt\\n" > pystachy\n')
            with (root / "make.log").open("w") as log:
                check_bootstrap_tier.make_bootstrap(root, environment(root), log)
            self.assertEqual((root / "pystachy").read_text(), "rebuilt\n")

    def run_make(self, tier=None, mismatch=""):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = (ROOT / "Makefile").read_text().split("\n# FILES:", 1)[0]
            (root / "Makefile").write_text(source)
            (root / "lib").mkdir()
            (root / "lib/_pystachy_cache.py").touch()
            (root / "runtime.c").touch()
            (root / "runtime.py").touch()
            fake = f"#!{sys.executable}\n" + '''import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
output = Path(args[args.index("-o") + 1])
with open("commands.jsonl", "a") as log:
    log.write(json.dumps([sys.argv[0], args[0], os.getenv("PYSTACHY_AOT_OPT")]) + "\\n")
if args[0] == "build":
    output.write_bytes(Path(__file__).read_bytes())
    output.chmod(0o755)
    Path(args[args.index("--emit-ir") + 1]).write_text("compiler witness\\n")
else:
    text = "compiler witness\\n" if args[0] == "ir" else "runtime witness\\n"
    if os.getenv("BOOTSTRAP_TEST_MISMATCH") == output.name:
        text = "wrong witness\\n"
    output.write_text(text)
'''
            (root / "pystachy.py").write_text(fake)
            env = environment(root) | {"PYSTACHY_AOT_OPT": "0", "BOOTSTRAP_TEST_MISMATCH": mismatch}
            command = ["make", "pystachy", f"PY={sys.executable}"]
            if tier is not None:
                command.append("BOOTSTRAP_AOT_OPT=" + tier)
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=15)
            calls = [json.loads(line) for line in (root / "commands.jsonl").read_text().splitlines()]
            return result, calls, (root / "pystachy").exists()

    def test_opt_in_changes_only_temporary_compiler_and_default_remains_o2(self):
        for tier in (None, "0", "1", "2"):
            with self.subTest(tier=tier):
                result, calls, installed = self.run_make(tier)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                builds = [call for call in calls if call[1] == "build"]
                self.assertEqual([call[2] for call in builds], [tier or "2", "2"])
                self.assertEqual([call[1] for call in calls], ["build", "build", "ir", "rt", "rt", "rt"])
                self.assertTrue(installed)

    def test_both_fixed_points_are_required_before_installing_final_compiler(self):
        for mismatch in ("stage3.ll", "rt2.ll"):
            with self.subTest(mismatch=mismatch):
                result, _, installed = self.run_make("1", mismatch)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(installed)


@unittest.skipUnless(os.environ.get("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for real tier builds")
class RealTierBuilds(unittest.TestCase):
    def test_all_tiers_keep_output_and_raw_ir_for_scalar_and_allocating_programs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = environment(root) | {"PYSTACHY_LLVM": os.environ["PYSTACHY_TEST_LLVM"]}
            native = os.environ.get("PYSTACHY_TEST_COMPILER")
            compiler = [native] if native else [sys.executable, str(ROOT / "pystachy.py")]
            for index, program in enumerate(PROGRAMS):
                source = root / f"source_{index}.py"
                source.write_text(program)
                oracle = subprocess.run([sys.executable, str(source)], env=env,
                                        capture_output=True, check=True, timeout=10)
                raw = subprocess.run(compiler + ["ir", str(source)], cwd=ROOT, env=env,
                                     capture_output=True, check=True, timeout=30).stdout
                for tier in ("0", "1", "2"):
                    with self.subTest(program=index, tier=tier):
                        output, witness = root / f"output_{index}_{tier}", root / f"ir_{index}_{tier}.ll"
                        built = subprocess.run(compiler + ["build", str(source), "-o", str(output),
                                                           "--emit-ir", str(witness)], cwd=ROOT,
                                               env=env | {"PYSTACHY_AOT_OPT": tier},
                                               capture_output=True, timeout=120)
                        self.assertEqual(built.returncode, 0, built.stderr)
                        self.assertEqual(witness.read_bytes(), raw)
                        for stress in (False, True):
                            actual = subprocess.run([str(output)], env=env | ({"PYSTACHY_GC_STRESS": "1"} if stress else {}),
                                                    capture_output=True, timeout=30)
                            self.assertEqual((actual.returncode, actual.stdout, actual.stderr),
                                             (oracle.returncode, oracle.stdout, oracle.stderr))


if __name__ == "__main__":
    unittest.main()
