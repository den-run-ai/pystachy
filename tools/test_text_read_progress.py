"""Text read(n) must return without probing beyond its completed character.

Set PYSTACHY_TEXT_READ_COMPILER to a compiler command to compare CPython with
fresh native JIT/AOT programs. Tests keep the write pipe open until after each
expected answer; writing all input then closing would hide the regression.
"""

import os
from pathlib import Path
import selectors
import shlex
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''import sys

if sys.argv[1] == "stdin":
    stream = sys.stdin
else:
    newline: str | None = None
    if sys.argv[3] == "empty":
        newline = ""
    elif sys.argv[3] == "lf":
        newline = "\\n"
    elif sys.argv[3] == "cr":
        newline = "\\r"
    elif sys.argv[3] == "crlf":
        newline = "\\r\\n"
    stream = open("/dev/stdin", encoding=sys.argv[2], newline=newline)
print("ready")
sys.stdout.flush()
if sys.argv[4] == "zero":
    print(repr(stream.read(0)))
    sys.stdout.flush()
for index in range(3):
    print(repr(stream.read(1)))
    sys.stdout.flush()
'''


class LiveReader:
    def __init__(self, command, options, env):
        self.process = subprocess.Popen(command + options, cwd=ROOT, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = bytearray()

    def line(self, timeout=2):
        if b"\n" not in self.buffer:
            if not self.selector.select(timeout):
                raise AssertionError("text read waited beyond its complete character while the pipe stayed open")
            chunk = os.read(self.process.stdout.fileno(), 4096)
            if not chunk:
                raise AssertionError("text reader exited before its answer")
            self.buffer.extend(chunk)
        if b"\n" not in self.buffer:
            raise AssertionError("text reader returned an incomplete protocol answer")
        answer, _, remainder = self.buffer.partition(b"\n")
        self.buffer[:] = remainder
        return bytes(answer)

    def send(self, data):
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def quiet(self):
        return not self.buffer and not self.selector.select(0.05)

    def close(self):
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.communicate(timeout=5)
        self.selector.close()


@unittest.skipUnless(sys.platform.startswith("linux"), "live /dev/stdin pipe checks currently target Linux")
class TextReadProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pystachy-text-read-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.source = cls.directory / "reader.py"
        cls.source.write_text(PROGRAM)
        cls.env = os.environ.copy()
        cls.env["PYTHONIOENCODING"] = "utf-8"
        cls.commands = {"cpython": [sys.executable, str(cls.source)]}
        native = os.environ.get("PYSTACHY_TEXT_READ_COMPILER")
        if native:
            compiler = shlex.split(native)
            binary = cls.directory / "reader"
            subprocess.run(compiler + ["build", str(cls.source), "-o", str(binary)],
                           cwd=ROOT, env=cls.env, capture_output=True, check=True, timeout=180)
            cls.commands["aot"] = [str(binary)]
            cls.commands["jit"] = compiler + ["run", str(cls.source)]

    def reader(self, command, kind="file", encoding="utf-8", newline="lf", zero=False):
        reader = LiveReader(command, [kind, encoding, newline, "zero" if zero else "nonzero"], self.env)
        self.addCleanup(reader.close)
        self.assertEqual(reader.line(timeout=120), b"ready")
        return reader

    def test_read_zero_does_not_wait_for_any_input(self):
        for mode, command in self.commands.items():
            for kind in ("stdin", "file"):
                with self.subTest(mode=mode, kind=kind):
                    reader = self.reader(command, kind=kind, zero=True)
                    self.assertEqual(reader.line(), b"''")

    def test_ascii_and_newline_return_without_following_byte(self):
        for mode, command in self.commands.items():
            for kind in ("stdin", "file"):
                with self.subTest(mode=mode, kind=kind):
                    reader = self.reader(command, kind=kind)
                    for data, expected in ((b"A", "A"), (b"\n", "\n"), (b"B", "B")):
                        reader.send(data)
                        self.assertEqual(reader.line(), repr(expected).encode())

    def test_utf8_waits_for_continuations_but_not_next_character(self):
        for mode, command in self.commands.items():
            for character in ("é", "雪", "🚠"):
                with self.subTest(mode=mode, character=character):
                    reader = self.reader(command)
                    encoded = character.encode()
                    reader.send(encoded[:1])
                    self.assertTrue(reader.quiet(), "incomplete UTF-8 character returned early")
                    reader.send(encoded[1:])
                    self.assertEqual(reader.line(), repr(character).encode())
                    reader.send(b"Z")
                    self.assertEqual(reader.line(), b"'Z'")

    def test_latin1_high_byte_is_a_complete_character(self):
        for mode, command in self.commands.items():
            with self.subTest(mode=mode):
                reader = self.reader(command, encoding="latin-1")
                for data, expected in ((b"\xe9", "é"), (b"\xff", "ÿ"), (b"Q", "Q")):
                    reader.send(data)
                    self.assertEqual(reader.line(), repr(expected).encode())

    def test_universal_newlines_keep_required_carriage_return_lookahead(self):
        for mode, command in self.commands.items():
            for newline in ("none", "empty"):
                with self.subTest(mode=mode, newline=newline):
                    reader = self.reader(command, newline=newline)
                    reader.send(b"\r")
                    self.assertTrue(reader.quiet(), "pending universal-newline CR returned early")
                    reader.send(b"\n")
                    self.assertEqual(reader.line(), b"'\\n'" if newline == "none" else b"'\\r'")
                    if newline == "empty":
                        self.assertEqual(reader.line(), b"'\\n'")
                    reader.send(b"Q")
                    self.assertEqual(reader.line(), b"'Q'")

    def test_explicit_newline_modes_do_not_probe_after_carriage_return(self):
        for mode, command in self.commands.items():
            for newline in ("lf", "cr", "crlf"):
                with self.subTest(mode=mode, newline=newline):
                    reader = self.reader(command, newline=newline)
                    reader.send(b"\r")
                    self.assertEqual(reader.line(), b"'\\r'")
                    reader.send(b"X")
                    self.assertEqual(reader.line(), b"'X'")


if __name__ == "__main__":
    unittest.main()
