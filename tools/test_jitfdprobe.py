"""JIT setting rejection, the descriptor probe's launcher and report comparison."""

import contextlib
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jitfdprobe import BOOTSTRAP, normalized

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler import driver


class CachePreparationReached(Exception):
    pass


class DriverSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="pystachy-launch-settings-")
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / "program.py"
        self.source.write_text("print(42)\n")
        self.addCleanup(sys.setrecursionlimit, sys.getrecursionlimit())

    def launch(self, value, command="run"):
        arguments = [str(Path(driver.__file__).resolve().parents[2] / "pystachy.py"), command, str(self.source)]
        with patch.object(sys, "argv", arguments), patch.dict(os.environ, {"PYSTACHY_JIT_INLINE": value}, clear=True), \
                patch.object(driver.diagnostics, "SRC", ""), \
                patch.object(driver.cached_run, "prepare", side_effect=CachePreparationReached):
            driver.main()

    def test_invalid_inline_settings_reject_before_cache_acquisition(self):
        for value in ("", "invalid", "-1", "+1", " 1", "1.5"):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit) as stopped:
                    self.launch(value)
                self.assertEqual(stopped.exception.code, 1)
                self.assertIn("PYSTACHY_JIT_INLINE", error.getvalue())

    def test_unicode_digits_keep_the_existing_int_conversion(self):
        # Superscript two passes isdigit(), but int() raises ValueError.
        with self.assertRaises(ValueError):
            self.launch("\N{SUPERSCRIPT TWO}")
        for value in ("0", "20000", "\N{ARABIC-INDIC DIGIT TWO}", "9" * 80):
            with self.subTest(value=value), self.assertRaises(CachePreparationReached):
                self.launch(value)

    def test_hosted_integer_digit_limit_is_preserved_before_cache_acquisition(self):
        previous = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(640)
            with self.assertRaises(ValueError):
                self.launch("9" * 641)
        finally:
            sys.set_int_max_str_digits(previous)

    def test_other_compilation_commands_ignore_the_jit_setting(self):
        for command in ("ir", "build", "ext"):
            with self.subTest(command=command), self.assertRaises(CachePreparationReached):
                self.launch("", command)


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

    def test_reports_ignore_process_ids_and_only_a_removed_jitdump(self):
        dump = b"fd 5 /tmp/tmpx/.debug/jit/llvm-IR-jit-20261109-abcdef/jit-123.dump (deleted)\n"
        report = b"fd 1 /proc/123/fd/pipe:[456]\nfd 3 /proc/123/fd/3\n" + dump
        self.assertEqual(normalized(report, mcjit=True), b"fd 1 /proc/PID/fd/pipe:[]\nfd 3 /proc/PID/fd/3\n")
        self.assertIn(b"jit-123.dump", normalized(report))
        self.assertIn(b"jit-123.dump", normalized(report.replace(b" (deleted)", b""), mcjit=True))
        with self.assertRaises(AssertionError):
            normalized(report + dump.replace(b"fd 5", b"fd 6"), mcjit=True)


if __name__ == "__main__":
    unittest.main()
