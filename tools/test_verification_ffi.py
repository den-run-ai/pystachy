"""FFI recordings normalize loader directories without hiding ABI failures."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FFIDiagnosticTests(unittest.TestCase):
    def capture(self, message, status=1):
        # Exercise the actual shell capture helper without running the native
        # FFI suite or replacing its Python-free comparison path.
        runner = (ROOT / "tests/ffi/run.sh").read_text()
        start = runner.index("\ncerr() {") + 1
        end = runner.index('\nif [ "$1" = --record ]; then', start)
        shell = runner[start:end] + '\ncerr "$1" "$2"\n'
        with tempfile.TemporaryDirectory(prefix="pystachy-ffi-diagnostic-") as folder:
            output = Path(folder) / "case.out"
            stderr = Path(folder) / "case.err"
            output.write_text(f"before\n[exit {status}]\n")
            stderr.write_text("Traceback omitted here\n" + message + "\n")
            subprocess.run(["sh", "-c", shell, "capture", str(output), str(stderr)], check=True, timeout=10)
            return output.read_text()

    def test_absolute_libm_loader_directories_are_canonicalized(self):
        for directory in ("/lib/x86_64-linux-gnu", "/lib/aarch64-linux-gnu", "/usr/lib64"):
            with self.subTest(directory=directory):
                error = f"AttributeError: {directory}/libm.so.6: undefined symbol: no_such_function_here"
                self.assertEqual(self.capture(error), "before\n[exit 1]\n[stderr] AttributeError: "
                                 "libm.so.6: undefined symbol: no_such_function_here\n")

    def test_normalization_preserves_semantic_mismatches(self):
        for message in (
                "OSError: /lib/aarch64-linux-gnu/libm.so.6: undefined symbol: no_such_function_here",
                "AttributeError: /lib/aarch64-linux-gnu/libm.so.5: undefined symbol: no_such_function_here",
                "AttributeError: /lib/aarch64-linux-gnu/libc.so.6: undefined symbol: no_such_function_here",
                "AttributeError: /lib/aarch64-linux-gnu/libm.so.6: another loader failure",
                "AttributeError: libm.so.6: undefined symbol: no_such_function_here"):
            with self.subTest(message=message):
                self.assertEqual(self.capture(message), "before\n[exit 1]\n[stderr] " + message + "\n")
        self.assertEqual(self.capture("AttributeError: /lib/aarch64-linux-gnu/libm.so.6: undefined symbol: wrong_symbol", 2),
                         "before\n[exit 2]\n[stderr] AttributeError: libm.so.6: undefined symbol: wrong_symbol\n")

    def test_success_does_not_add_stderr_to_recording(self):
        self.assertEqual(self.capture("warning", 0), "before\n[exit 0]\n")


if __name__ == "__main__":
    unittest.main()
