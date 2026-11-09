"""The descriptor probe's launcher and report comparison."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from jitfdprobe import BOOTSTRAP, normalized


@unittest.skipUnless(sys.platform == "linux", "the descriptor probe runs on Linux")
class LauncherTests(unittest.TestCase):
    def launch(self, descriptors, command, program, *arguments, environment=None):
        with tempfile.TemporaryDirectory(prefix="jitfd-launch-") as temporary:
            root = Path(temporary)
            launch = root / "launch.py"
            launch.write_text(BOOTSTRAP)
            bindir = root / "bin"
            bindir.mkdir()
            (bindir / "python3").symlink_to(sys.executable)
            return subprocess.run(
                [sys.executable, str(launch), descriptors, command, "-c", program, *arguments],
                cwd=root, env=os.environ | {"PATH": str(bindir)} | (environment or {}),
                capture_output=True, text=True, timeout=10,
            )

    def run_launcher(self, bare):
        program = """import os
import sys
for value in sys.argv[1:]:
    descriptor = int(value)
    assert os.get_inheritable(descriptor), descriptor
    print(descriptor, os.read(descriptor, 100).decode())
"""
        result = self.launch("7,8,9,64", "python3" if bare else sys.executable, program, "7", "8", "9", "64")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "7 pipe-7\n8 pipe-8\n9 pipe-9\n64 pipe-64\n")
        self.assertEqual(result.stderr, "")

    def test_bare_command_is_resolved_through_path(self):
        self.run_launcher(bare=True)

    def test_absolute_command_keeps_inherited_descriptors(self):
        self.run_launcher(bare=False)

    def test_standard_streams_close_and_sigint_dispositions_apply(self):
        program = """import os
import signal
ignored = signal.getsignal(signal.SIGINT) == signal.SIG_IGN
os.write(1, f"{os.path.exists('/proc/self/fd/0')} {os.path.exists('/proc/self/fd/2')} {ignored} {'JITFD_SIGINT' in os.environ}".encode())
"""
        inherited = signal.getsignal(signal.SIGINT) == signal.SIG_IGN  # (no JITFD_SIGINT: unchanged)
        for disposition, ignored in (("ignore", True), ("default", False), ("handler", False), ("", inherited)):
            with self.subTest(disposition=disposition):
                result = self.launch("0,2", sys.executable, program, environment={"JITFD_SIGINT": disposition})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout, f"False False {ignored} False")

    def test_reports_ignore_process_ids_and_keep_every_descriptor(self):
        # Every JIT launch must match CPython's table exactly: a deleted file that lli kept open,
        # such as a perf jitdump, stays in the report and fails the comparison.
        report = b"fd 1 /proc/123/fd/pipe:[456]\nfd 3 /proc/123/fd/3\n"
        self.assertEqual(normalized(report), b"fd 1 /proc/PID/fd/pipe:[]\nfd 3 /proc/PID/fd/3\n")
        dump = b"fd 5 /tmp/tmpx/.debug/jit/llvm-IR-jit-20261109-abcdef/jit-123.dump (deleted)\n"
        self.assertEqual(normalized(report + dump), normalized(report) + dump)
        self.assertNotEqual(normalized(report + dump), normalized(report))


if __name__ == "__main__":
    unittest.main()
