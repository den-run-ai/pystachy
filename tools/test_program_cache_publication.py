"""Execution-access and two-pass link-input regressions for native publication."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import cached_run
from src.pystachy_compiler import program_cache as pc


@unittest.skipUnless(sys.platform == "linux", "the initial native cache supports Linux")
class ProgramCachePublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.source = self.root / "main.py"
        self.source.write_text("print(41)\n")
        self.executable = self.root / "native"
        self.executable.write_bytes(b"\x7fELF\x00publication-test\n")
        self.executable.chmod(0o700)
        self.obj = self.root / "program.o"
        self.runtime = self.root / "runtime.o"
        self.dependency = self.root / "dependency.o"
        self.other = self.root / "other.o"
        for path in (self.obj, self.runtime, self.dependency, self.other):
            path.write_bytes(b"original object\n")
        self.first = self.root / "discovery-link"
        self.second = self.root / "final-link"
        self.context = "publication-regression"
        pc.STATIC_MEMO.clear()
        pc.MEMO_ROOT[0] = ""
        pc.start()
        pc.track_source(str(self.source), self.source.read_text())
        self.addCleanup(pc.stop)

    def write_trace(self, path, inputs):
        path.write_text("\n".join(str(p) for p in (self.obj, self.runtime, *inputs)) + "\n")

    def record_trace(self, path):
        self.assertTrue(cached_run.link_inputs(str(path), str(self.obj), str(self.runtime)))

    def publish(self):
        return pc.publish(str(self.cache), self.context, str(self.executable))

    def test_noexec_mount_rejects_cold_publication_and_cleans_stage(self):
        # Mode 0700 does not grant execution on a noexec mount. Simulate the
        # shell's access check while still performing the real copy and chmod.
        # This needs neither a privileged mount nor a particular /dev/shm setup.
        shell = pc._sh
        denied = []

        def noexec(command):
            if "[ -x " not in command:
                return shell(command)
            checked = shlex.split(command[command.index("[ -x "):])[2]
            self.assertFalse(shell(command.replace("[ -x ", "[ ! -e ")))
            self.assertTrue(Path(checked).is_file())
            self.assertEqual(Path(checked).stat().st_mode & 0o777, 0o700)
            denied.append(checked)
            return False

        with patch.object(pc, "_sh", side_effect=noexec):
            self.assertEqual(self.publish(), "")
        self.assertEqual(len(denied), 1)
        private = self.cache / "program-v1"
        self.assertEqual(list(private.glob("*.manifest")), [])
        self.assertEqual(list(private.glob("*.exe")), [])
        self.assertEqual(list(private.glob("stage-*")), [])

    def test_unchanged_link_inputs_allow_publication(self):
        self.write_trace(self.first, [self.dependency, self.other])
        self.write_trace(self.second, [self.dependency, self.other])
        self.record_trace(self.first)
        self.assertTrue(cached_run.same_link_inputs(str(self.first), str(self.second)))
        self.record_trace(self.second)
        target = self.publish()
        self.assertTrue(target)
        self.assertEqual(pc.lookup(str(self.cache), self.context), target)

    def test_changed_link_resolution_or_order_declines(self):
        self.write_trace(self.first, [self.dependency, self.other])
        added = self.root / "added.o"
        added.write_bytes(b"newly selected object\n")
        for inputs in ([self.dependency], [self.other],
                       [self.dependency, self.other, added],
                       [self.dependency, self.other, self.other],
                       [self.other, self.dependency]):
            with self.subTest(inputs=inputs):
                self.write_trace(self.second, inputs)
                self.assertFalse(cached_run.same_link_inputs(str(self.first), str(self.second)))

    def test_missing_or_unreadable_link_trace_declines(self):
        self.write_trace(self.first, [self.dependency])
        self.assertFalse(cached_run.same_link_inputs(str(self.first), str(self.second)))
        self.assertFalse(cached_run.same_link_inputs(str(self.second), str(self.first)))
        self.second.mkdir()
        self.assertFalse(cached_run.same_link_inputs(str(self.first), str(self.second)))

    def test_same_paths_with_changed_bytes_after_discovery_cannot_publish(self):
        self.write_trace(self.first, [self.dependency])
        self.write_trace(self.second, [self.dependency])
        self.record_trace(self.first)
        before = self.dependency.stat()
        self.dependency.write_bytes(b"modified object\n")
        os.utime(self.dependency, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.dependency.stat().st_size, before.st_size)
        self.assertTrue(cached_run.same_link_inputs(str(self.first), str(self.second)))
        self.record_trace(self.second)
        self.assertEqual(self.publish(), "")
        self.assertEqual(pc.lookup(str(self.cache), self.context), "")

    def test_native_link_input_replaced_after_final_link_cannot_publish(self):
        cc = shutil.which("cc")
        if cc is None:
            self.skipTest("a host C compiler is needed for the isolated native link probe")

        def compile_object(name, body, output):
            source = self.root / name
            source.write_text(body)
            subprocess.run([cc, "-c", str(source), "-o", str(output)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

        def link(output, trace):
            result = subprocess.run([cc, str(self.obj), str(self.runtime), str(self.dependency),
                                     "-Wl,-t", "-o", str(output)], check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            trace.write_bytes(result.stdout)

        compile_object("main.c", "int answer(void); int main(void) { return answer(); }\n", self.obj)
        compile_object("runtime.c", "void runtime_marker(void) {}\n", self.runtime)
        compile_object("answer.c", "int answer(void) { return 41; }\n", self.dependency)
        link(self.executable, self.first)
        self.record_trace(self.first)
        link(self.executable, self.second)

        # The linker has consumed the old object. Replace it before the final
        # trace is checked, modelling a toolchain update at exactly that boundary.
        replacement = self.root / "replacement.o"
        compile_object("replacement.c", "int answer(void) { return 42; }\n", replacement)
        os.replace(replacement, self.dependency)
        self.assertEqual(subprocess.run([str(self.executable)], check=False, timeout=10).returncode, 41)
        current = self.root / "current-native"
        link(current, self.root / "current-link")
        self.assertEqual(subprocess.run([str(current)], check=False, timeout=10).returncode, 42)

        self.assertTrue(cached_run.same_link_inputs(str(self.first), str(self.second)))
        self.record_trace(self.second)
        self.assertEqual(self.publish(), "")
        self.assertEqual(pc.lookup(str(self.cache), self.context), "")


if __name__ == "__main__":
    unittest.main()
