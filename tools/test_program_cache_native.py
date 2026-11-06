#!/usr/bin/env python3
"""Compare the private native cache lock with CPython's OS-backed lock operations."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LLVM = os.environ.get("PYSTACHY_LLVM", "")
HAVE_LLVM = all(shutil.which(str(Path(LLVM) / tool) if LLVM else tool)
                for tool in ("clang", "opt", "lli", "llvm-link", "llvm-as"))
PROGRAM = '''import os
import sys
from _pystachy_cache import file_hash, try_lock

path, previous, mode = sys.argv[1], sys.argv[2], sys.argv[3]
if mode == "nul" or mode == "hash-nul":
    path += "\\0suffix"
if mode == "hash" or mode == "hash-nul":
    print(file_hash(path, int(previous)))
elif mode == "hash-repeat":
    before = sorted(os.listdir("/proc/self/fd"))
    for i in range(20):
        file_hash(path, int(previous))
        file_hash(path, 0)
        file_hash(path + "/missing", int(previous))
    print(before == sorted(os.listdir("/proc/self/fd")))
else:
    status = try_lock(path)
    expected = path if status == 1 else previous
    try:
        correct_descriptor = os.path.samefile("/proc/self/fd/9", expected)
    except OSError:
        correct_descriptor = False
    print(status, correct_descriptor, flush=True)
    if mode == "hold":
        copies = 0
        for name in os.listdir("/proc/self/fd"):
            try:
                if os.path.samefile("/proc/self/fd/" + name, expected):
                    copies += 1
            except OSError:
                pass
        print("copies", copies, flush=True)
        input()
    elif mode == "exec":
        os.execv("/bin/sh", ["sh", "-c", "if [ -e /proc/self/fd/9 ]; then printf 'leaked\\\\n'; else printf 'exec-ready\\\\n'; fi; IFS= read -r line; exit 0"])
'''

# Independent reference: CPython's public descriptor and flock operations.
ORACLE = '''import fcntl
import os
import stat

NATIVE = False

def file_hash(path, limit):
    from unittest.mock import patch
    from src.pystachy_compiler import program_cache as pc
    with patch.object(pc, \"MAX_BINARY\", limit):
        return pc._file_hash(path)

def try_lock(path):
    descriptor = -1
    acquired = False
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
        identity = os.fstat(descriptor)
        if not stat.S_ISREG(identity.st_mode) or identity.st_uid != os.geteuid():
            return -1
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if descriptor != 9:
            os.dup2(descriptor, 9, inheritable=False)
        else:
            os.set_inheritable(9, False)
        acquired = True
        return 1
    except (OSError, ValueError):
        return -1
    finally:
        if descriptor >= 0 and (descriptor != 9 or not acquired):
            os.close(descriptor)
'''
# Set inherited descriptors in a separate process, without changing the test runner's.
BOOTSTRAP = '''import fcntl
import os
import sys

setup, previous = sys.argv[1:3]
if setup == "fill":
    for expected in range(3, 9):
        descriptor = os.open(os.devnull, os.O_RDONLY)
        assert descriptor == expected, (descriptor, expected)
        os.set_inheritable(descriptor, True)
else:
    descriptor = os.open(previous, os.O_RDONLY)
    os.dup2(descriptor, 9, inheritable=True)
    if descriptor != 9:
        os.close(descriptor)
    if setup == "locked":
        fcntl.flock(9, fcntl.LOCK_EX)
os.execv(sys.argv[3], sys.argv[3:])
'''


@unittest.skipUnless(sys.platform == "linux" and HAVE_LLVM, "Linux and complete LLVM are required")
class NativeProgramCacheLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="pystachy-native-cache-lock-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        cls.program = cls.work / "lock_probe.py"
        cls.program.write_text(PROGRAM)
        cls.oracle = cls.work / "oracle"
        cls.oracle.mkdir()
        (cls.oracle / "_pystachy_cache.py").write_text(ORACLE)
        cls.bootstrap = cls.work / "bootstrap.py"
        cls.bootstrap.write_text(BOOTSTRAP)
        cls.environment = {key: value for key, value in os.environ.items()
                           if not key.startswith("PYSTACHY_") and key != "PYTHONPATH"}
        cls.environment.update(PYSTACHY_LLVM=LLVM, PYSTACHY_PROGRAM_CACHE="0",
                               PYSTACHY_CACHE=str(cls.work / "runtime-cache"))
        cls.executable = cls.work / "lock_probe"
        result = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "build", str(cls.program),
                                 "-o", str(cls.executable)], cwd=ROOT, capture_output=True, text=True,
                                env=cls.environment, timeout=120)
        if result.returncode:
            raise AssertionError(result.stderr)

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.work, prefix="case-")
        self.addCleanup(self.case.cleanup)
        self.base = Path(self.case.name)
        self.previous = self.base / "previous"
        self.previous.touch()
        self.lock = self.base / "lock"
        self.lock.touch()

    def spawn(self, native, path=None, mode="once", setup="previous", value=None):
        command = [str(self.executable)] if native else [sys.executable, str(self.program)]
        environment = self.environment.copy()
        if not native:
            environment["PYTHONPATH"] = str(self.oracle) + os.pathsep + str(ROOT)
        return subprocess.Popen([sys.executable, str(self.bootstrap), setup, str(self.previous),
                                 *command, str(path or self.lock), str(self.previous if value is None else value), mode],
                                env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def compare(self, expected, path=None, mode="once", setup="previous", value=None):
        for native in (False, True):
            with self.subTest(native=native), self.spawn(native, path, mode, setup, value) as child:
                output, error = child.communicate(timeout=10)
                self.assertEqual((child.returncode, output, error), (0, expected + "\n", ""))

    def line(self, child):
        result = bytearray()
        deadline = time.monotonic() + 10
        while not result.endswith(b"\n"):
            ready, _, _ = select.select([child.stdout], [], [], max(0, deadline - time.monotonic()))
            self.assertTrue(ready, "child did not report its lock state")
            part = os.read(child.stdout.fileno(), 1)
            if not part:
                break
            result.extend(part)
        return result.decode()

    def busy(self, path):
        with open(path) as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            return False

    def finish(self, child):
        output, error = child.communicate("done\n", timeout=10)
        self.assertEqual((child.returncode, output, error), (0, "", ""))

    def test_acquired_lock_replaces_descriptor_nine(self):
        self.compare("1 True")

    def test_open_returning_descriptor_nine_keeps_the_lock(self):
        self.compare("1 True", setup="fill")

    def test_busy_lock_preserves_existing_descriptor_nine(self):
        with open(self.lock) as owner:
            fcntl.flock(owner, fcntl.LOCK_EX)
            self.compare("0 True")

    def test_unusable_paths_preserve_existing_descriptor_nine(self):
        link = self.base / "symlink"
        link.symlink_to(self.lock)
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        for path in (self.base / "missing", self.base, link, fifo):
            with self.subTest(path=path.name):
                self.compare("-1 True", path)
        self.compare("-1 True", mode="nul")

    @unittest.skipUnless(os.geteuid() == 0, "changing a fixture owner requires root")
    def test_wrong_owner_is_unusable(self):
        try:
            os.chown(self.lock, 1, -1)
        except OSError as error:
            self.skipTest("fixture ownership cannot change in this namespace: " + str(error))
        self.compare("-1 True")

    def test_acquisition_closes_temporary_descriptor_and_releases_previous_lock(self):
        for native in (False, True):
            with self.subTest(native=native), self.spawn(native, mode="hold", setup="locked") as child:
                self.assertEqual(self.line(child), "1 True\n")
                self.assertTrue(self.busy(self.lock))
                self.assertFalse(self.busy(self.previous))
                self.assertEqual(self.line(child), "copies 1\n")
                self.finish(child)

    def test_failed_acquisition_retains_the_previous_lock(self):
        for native in (False, True):
            with self.subTest(native=native), self.spawn(native, self.base / "missing", "hold", "locked") as child:
                self.assertEqual(self.line(child), "-1 True\n")
                self.assertTrue(self.busy(self.previous))
                self.assertEqual(self.line(child), "copies 1\n")
                self.finish(child)

    def test_exec_releases_the_lock_while_process_remains_alive(self):
        for native in (False, True):
            with self.subTest(native=native), self.spawn(native, mode="exec") as child:
                self.assertEqual(self.line(child), "1 True\n")
                self.assertEqual(self.line(child), "exec-ready\n")
                self.assertIsNone(child.poll())
                self.assertFalse(self.busy(self.lock))
                self.finish(child)

    def test_killed_owner_releases_the_lock(self):
        for native in (False, True):
            with self.subTest(native=native), self.spawn(native, mode="hold") as child:
                self.assertEqual(self.line(child), "1 True\n")
                self.assertTrue(self.busy(self.lock))
                self.assertEqual(self.line(child), "copies 1\n")
                child.kill()
                child.communicate(timeout=10)
                self.assertFalse(self.busy(self.lock))

    def test_native_hash_preserves_binary_digest_and_size_limits(self):
        sys.path.insert(0, str(ROOT))
        from src.pystachy_compiler import program_cache as pc
        path = self.base / "bytes"
        for data in (b"", bytes(range(256)) * 257 + b"\x00\xff\r\n", b"x" * 196625):
            path.write_bytes(data)
            digest = pc.fnv(data.decode("latin-1"))
            self.compare(digest, path, "hash", value=len(data))
            self.compare("", path, "hash", value=len(data) - 1)
        self.compare("True", path, "hash-repeat", value=len(data))

    def test_native_hash_follows_regular_symlinks_and_rejects_unusable_paths(self):
        path = self.base / "bytes"
        path.write_bytes(b"abc")
        link = self.base / "link"
        link.symlink_to(path)
        self.compare("e71fa2190541574b", link, "hash", value=3)
        path.unlink()
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        for item in (link, self.base, fifo, self.base / "missing"):
            self.compare("", item, "hash", value=100)
        self.compare("", self.lock, "hash-nul", value=100)
        self.compare("", Path("/proc/self/cmdline"), "hash", value=1)

    def test_primitive_rejects_direct_and_shadow_module_calls(self):
        directory = self.base / "shadow"
        directory.mkdir()
        program = directory / "probe.py"
        for source in ('print(__pys_cache_lock("path"))\n',
                       'from _pystachy_cache import try_lock\nprint(try_lock("path"))\n'):
            program.write_text(source)
            (directory / "_pystachy_cache.py").write_text(
                'def try_lock(path: str) -> int:\n    return __pys_cache_lock(path)\n')
            result = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "ir", str(program),
                                     "-o", str(directory / "probe.ll")], cwd=ROOT, capture_output=True,
                                    text=True, env=self.environment, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertIn("name '__pys_cache_lock' is not defined", result.stderr)


if __name__ == "__main__":
    unittest.main()
