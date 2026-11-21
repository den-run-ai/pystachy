"""The syntax hook checks every path in a pre-commit batch."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parent.parent


class PreCommitCheckTests(unittest.TestCase):
    def test_mixed_batch_and_repaired_files(self):
        manifest = yaml.safe_load((ROOT / ".pre-commit-hooks.yaml").read_text())
        hook = next(item for item in manifest if item["id"] == "pystachy-check")
        with tempfile.TemporaryDirectory() as tmp:
            files = ["spaced good.py", "first broken.py", "-second.py"]
            command = [ROOT / hook["entry"], *files]
            # A syntax check may read this file but must never execute it.
            (Path(tmp) / files[0]).write_text("raise AssertionError()\n")
            for name in files[1:]:
                (Path(tmp) / name).write_text("x =\n")
            rejected = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 1)
            for name in files[1:]:
                self.assertIn(f"{name}:1: error:", rejected.stderr)
                (Path(tmp) / name).write_text("x = 1\n")
            accepted = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            self.assertEqual((accepted.returncode, accepted.stdout, accepted.stderr), (0, "", ""))
