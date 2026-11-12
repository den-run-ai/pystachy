"""Native graph/clock controls for optional GC research counters."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LLVM = Path(os.environ.get("PYSTACHY_LLVM", "/usr/bin"))
CLANG = shutil.which(str(LLVM / "clang"))
LINK = shutil.which(str(LLVM / "llvm-link"))
OUTPUT = "gcprofileprobe: reachability and counters agree\n"


@unittest.skipUnless(CLANG and LINK, "clang and llvm-link are required for GC counter controls")
class GCProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        if "PYSTACHY_LLVM" in os.environ:
            cls.env["PYSTACHY_LLVM"] = os.environ["PYSTACHY_LLVM"]
        cls.runtime = (ROOT / "runtime.c").read_text()
        cls.run_command([sys.executable, "pystachy.py", "rt", "runtime.py", "-o", str(cls.work / "rt.ll")])
        cls.plain = cls.build("plain", cls.runtime, False)
        cls.profile = cls.build("profile", cls.runtime, True)

    @classmethod
    def run_command(cls, command):
        return subprocess.run(command, cwd=ROOT, env=cls.env, check=True, capture_output=True, text=True, timeout=120)

    @classmethod
    def build(cls, name, runtime, profile):
        directory = cls.work / name
        (directory / "tools").mkdir(parents=True)
        (directory / "runtime.c").write_text(runtime)
        shutil.copyfile(ROOT / "tools/gcprofileprobe.c", directory / "tools/gcprofileprobe.c")
        flags = ["-DPYSTACHY_GC_PROFILE"] if profile else []
        cls.run_command([CLANG, "-O2", "-Wall", "-Wextra", "-Werror", *flags, "-I", str(ROOT),
                         "-S", "-emit-llvm", str(directory / "tools/gcprofileprobe.c"), "-o", str(directory / "probe.ll")])
        cls.run_command([LINK, str(cls.work / "rt.ll"), str(directory / "probe.ll"), "-o", str(directory / "probe.bc")])
        cls.run_command([CLANG, "-O2", str(directory / "probe.bc"), "-o", str(directory / "probe"), "-lm"])
        return directory / "probe"

    def probe(self, executable, stats=False):
        env = self.env | ({"PYSTACHY_GC": "stats"} if stats else {})
        return subprocess.run([str(executable)], env=env, capture_output=True, text=True, timeout=20)

    def test_normal_output_and_activation(self):
        for executable in [self.plain, self.profile]:
            with self.subTest(executable=executable.name, profile=executable == self.profile):
                run = self.probe(executable)
                self.assertEqual((run.returncode, run.stdout, run.stderr), (0, OUTPUT, ""))
        run = self.probe(self.plain, True)
        self.assertEqual((run.returncode, run.stdout), (0, OUTPUT), run.stderr)
        self.assertRegex(run.stderr, r"^gc: 2 collections, 2\.0 ms; heap peak [0-9.]+ MiB; live [0-9.]+ MiB at the last\n$")

    def test_exact_work_and_phase_counts(self):
        run = self.probe(self.profile, True)
        self.assertEqual((run.returncode, run.stdout), (0, OUTPUT), run.stderr)
        lines = run.stderr.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("gc: 2 collections, 6.0 ms;"), lines[0])
        self.assertEqual(lines[1], "gc work: marked objects 9; scanned objects 7; root words 526; heap words 2066")
        self.assertEqual(lines[2], "gc phases: roots 2.000 ms; trace 2.000 ms; sweep 2.000 ms")

    def test_atomic_mark_count_negative_control(self):
        old = "if (gc_stats) gc_marked_objects++;"
        self.assertEqual(self.runtime.count(old), 1)
        changed = self.runtime.replace(old, "if (gc_stats && !(s->k & 1)) gc_marked_objects++;")
        run = self.probe(self.build("exclude-atomic", changed, True), True)
        self.assertEqual(run.returncode, 1)
        self.assertIn("marked objects must include atomic objects exactly once", run.stderr)

    def test_root_word_negative_control(self):
        old = "gc_root_words += gc_heap_words - words; gc_heap_words = words;"
        self.assertEqual(self.runtime.count(old), 1)
        changed = self.runtime.replace(old, "gc_root_words += gc_heap_words - words;")
        run = self.probe(self.build("retain-root-words", changed, True), True)
        self.assertEqual(run.returncode, 1)
        self.assertIn("heap words must include each scanned slot, without root words", run.stderr)


if __name__ == "__main__":
    unittest.main()
