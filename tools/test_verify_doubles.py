"""The harness doubles' shared bootstrap stage meets the real scripts it stands beside."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from verify_doubles import MAKE_SCRIPTS, ROOT, SCRIPTS, STAGE, copy_scripts

# a repository shell script that a recipe or the bootstrap block runs as a command
COMMAND = re.compile(r"(?:^|[\s;&|(])((?:tools|tests)/[A-Za-z0-9_/]+\.sh)\b")


def commands(text):
    return {match.group(1) for match in COMMAND.finditer(text)}


class SharedStage(unittest.TestCase):
    def double(self, directory, attempts):
        path = Path(directory) / "compiler"
        path.write_text(f"#!{sys.executable}\n{STAGE}import sys\nstage(sys.argv[1:], attempts={attempts})\n")
        path.chmod(0o755)
        return path

    def test_scripts_hold_what_the_bootstraps_run(self):
        verify = (ROOT / "tests/verify.sh").read_text()
        start = verify.index("\n# ---- bootstrap")
        block = verify[start : verify.index("\n# ---- ", start + 1)]
        self.assertIn("tools/self_compile_once.sh", commands(block))
        self.assertLessEqual(commands(block) | {"tests/corpus.sh"}, set(SCRIPTS))
        makefile = (ROOT / "Makefile").read_text()
        start = makefile.index("\npystachy: ")
        recipe = makefile[start : makefile.index("\n\n", start)]
        self.assertLessEqual(commands(recipe), set(MAKE_SCRIPTS))
        self.assertLessEqual(set(MAKE_SCRIPTS), set(SCRIPTS))

    def test_stage_meets_the_one_attempt_gate(self):
        for attempts, status in ((1, 0), (2, 1)):
            with self.subTest(attempts=attempts), tempfile.TemporaryDirectory() as directory:
                out = Path(directory) / "stage3.ll"
                env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
                result = subprocess.run([str(ROOT / "tools/self_compile_once.sh"), str(self.double(directory, attempts)),
                                         str(out)], cwd=directory, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, status, result.stderr)
                if status == 0:
                    self.assertEqual((out.read_text(), result.stderr), ("fixed point\n", ""))
                else:
                    self.assertIn(f"took {attempts} type-inference attempts", result.stderr)

    def test_stage_builds_a_copy_of_its_double(self):
        with tempfile.TemporaryDirectory() as directory:
            double = self.double(directory, 1)
            built = Path(directory) / "pystachy1"
            subprocess.run([str(double), "build", "pystachy.py", "-o", str(built)], check=True, timeout=30)
            self.assertEqual(built.read_bytes(), double.read_bytes())
            self.assertTrue(os.access(built, os.X_OK))
            copy_scripts(Path(directory))
            for name in SCRIPTS:
                self.assertEqual((Path(directory) / name).read_bytes(), (ROOT / name).read_bytes())
                self.assertEqual(os.access(Path(directory) / name, os.X_OK), os.access(ROOT / name, os.X_OK))


if __name__ == "__main__":
    unittest.main()
