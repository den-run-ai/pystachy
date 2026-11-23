"""The bootstrap's one-attempt check and the tool that names inference restarts."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "tools/self_compile_once.sh"
TOOL = ROOT / "tools/inference_restarts.py"

# A loop variable reused for another key type: the second loop's store restarts the program.
REUSED = """\
def run(names: list[str], ids: dict[int, bool]) -> None:
    keeps: dict[str, bool] = {}
    seen: dict[int, bool] = {}
    for k in names:
        keeps[k] = True
    for k in ids:
        seen[k] = True
    print(len(keeps), len(seen))


run(["a"], {1: True})
"""
RENAMED = REUSED.replace("for k in ids:\n        seen[k]", "for n in ids:\n        seen[n]")

# A stand-in for a bootstrap stage: FAKE_ATTEMPTS attempt records, a message and FAKE_STATUS.
FAKE = """#!/bin/sh
i=0
while [ "$i" -lt "${FAKE_ATTEMPTS:-1}" ]; do
  [ "${PYSTACHY_TIMING:-}" = 1 ] && printf 'pystachy-timing\\tprogram.attempt\\t0.5\\n' >&2
  i=$((i + 1))
done
[ "${PYSTACHY_TIMING:-}" = 1 ] && printf 'pystachy-timing\\tprogram.frontend\\t1.5\\n' >&2
echo "compiler message" >&2
echo "; $*" > "$4"
exit "${FAKE_STATUS:-0}"
"""


def environment(**extra):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    return env | extra


class SelfCompileOnce(unittest.TestCase):
    def check(self, **extra):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "compiler"
            fake.write_text(FAKE)
            fake.chmod(0o755)
            out = Path(directory) / "stage3.ll"
            result = subprocess.run([str(CHECK), str(fake), str(out)], cwd=ROOT, env=environment(**extra),
                                    capture_output=True, text=True, timeout=30)
            return result, out.read_text() if out.exists() else None

    def test_one_attempt_passes_and_keeps_other_messages(self):
        result, ir = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "compiler message\n")
        self.assertTrue(ir.startswith("; ir pystachy.py -o "), ir)

    def test_restarts_fail_and_name_the_tool(self):
        for attempts in ("0", "2", "3"):
            with self.subTest(attempts=attempts):
                result, _ = self.check(FAKE_ATTEMPTS=attempts)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f"took {attempts} type-inference attempts", result.stderr)
                self.assertIn("tools/inference_restarts.py", result.stderr)

    def test_compiler_failure_keeps_its_status_and_messages(self):
        result, _ = self.check(FAKE_STATUS="7")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stderr, "compiler message\n")

    def test_caller_timing_records_pass_through(self):
        result, _ = self.check(PYSTACHY_TIMING="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count("pystachy-timing\tprogram.attempt\t"), 1)
        self.assertIn("pystachy-timing\tprogram.frontend\t", result.stderr)
        self.assertIn("compiler message\n", result.stderr)


class InferenceRestarts(unittest.TestCase):
    def restarts(self, source):
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "program.py"
            program.write_text(textwrap.dedent(source))
            return subprocess.run([sys.executable, str(TOOL), str(program)], cwd=ROOT, env=environment(),
                                  capture_output=True, text=True, timeout=120)

    def test_names_the_join_and_the_error_that_restarted(self):
        result = self.restarts(REUSED)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len([line for line in lines if line.startswith("restart ")]), 1, result.stdout)
        self.assertRegex(lines[0], r"^restart 1: Rejoin after .*/program\.py:7: ")
        self.assertRegex(lines[1], r"^  join \S*run\|k: union\[int,str\]$")
        self.assertEqual(lines[-1], "2 inference attempts")

    def test_distinct_names_need_one_attempt(self):
        # (the negative control: the same program with the second loop's variable renamed)
        result = self.restarts(RENAMED)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "1 inference attempt\n")


if __name__ == "__main__":
    unittest.main()
