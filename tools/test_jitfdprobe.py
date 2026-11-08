"""The descriptor probe launcher accepts PATH commands and absolute paths."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jitfdprobe import BOOTSTRAP


@unittest.skipUnless(sys.platform == "linux", "the descriptor probe runs on Linux")
class LauncherTests(unittest.TestCase):
    def run_launcher(self, bare):
        with tempfile.TemporaryDirectory(prefix="jitfd-launch-") as temporary:
            root = Path(temporary)
            launch = root / "launch.py"
            launch.write_text(BOOTSTRAP)
            bindir = root / "bin"
            bindir.mkdir()
            (bindir / "python3").symlink_to(sys.executable)
            command = "python3" if bare else sys.executable
            program = """import os
import sys
for value in sys.argv[1:]:
    descriptor = int(value)
    assert os.get_inheritable(descriptor), descriptor
    print(descriptor, os.read(descriptor, 100).decode())
"""
            result = subprocess.run(
                [sys.executable, str(launch), "7,8,9,64", command, "-c", program,
                 "7", "8", "9", "64"],
                cwd=root, env=os.environ | {"PATH": str(bindir)},
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "7 pipe-7\n8 pipe-8\n9 pipe-9\n64 pipe-64\n")
            self.assertEqual(result.stderr, "")

    def test_bare_command_is_resolved_through_path(self):
        self.run_launcher(bare=True)

    def test_absolute_command_keeps_inherited_descriptors(self):
        self.run_launcher(bare=False)


if __name__ == "__main__":
    unittest.main()
