"""Bound the stack frames that a collection scans as roots.

mark_roots scans the stack conservatively, from its own frame up to main's, so the frames of the
allocator below it (gc_slow, with refill inlined, and collect) are scanned too, stale words
included: a word that an earlier call left there holding a dead object's address retains that
object and all it reaches. Inlining pages_settle into collect once made collect's frame 2 KiB
larger, and microGPT's last collection kept 20.6 MiB live instead of 14.7. The test compiles
runtime.c as the driver does (clang -O2 -fexceptions), with -fstack-usage, and bounds those
frames; its negative control lets pages_settle be inlined and expects the bound to catch it.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLANG = shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang")
SCANNED = ("gc_slow", "refill", "collect", "mark_roots")   # on the stack while marking scans it
REQUIRED = ("gc_slow", "collect")                         # out of line: noinline
BOUND = 256                                               # bytes; collect and gc_slow took 120 and 72


@unittest.skipUnless(CLANG, "clang is required for the runtime's stack frame bounds")
class RuntimeFrames(unittest.TestCase):
    def frames(self, source=None):
        with tempfile.TemporaryDirectory() as directory:
            path = ROOT / "runtime.c"
            if source is not None:          # beside a copy, its quoted includes come from -I
                path = Path(directory) / "runtime.c"
                path.write_text(source)
            result = subprocess.run([CLANG, "-O2", "-fexceptions", "-fstack-usage", "-c", str(path), "-I", str(ROOT),
                                     "-o", str(Path(directory) / "runtime.o"), "-Wno-unused-command-line-argument"],
                                    capture_output=True, text=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr[-4000:])
            usage = (Path(directory) / "runtime.su").read_text()
        frames = {}
        for line in usage.splitlines():
            match = re.match(r"^.*:(\w+)\t(\d+)\t(\S+)$", line)
            if match and match[1] in SCANNED:
                frames[match[1]] = (int(match[2]), match[3])
        return frames

    def test_frames_that_marking_scans_stay_small(self):
        frames = self.frames()
        for name in REQUIRED:
            self.assertIn(name, frames)
        for name, (size, kind) in frames.items():
            with self.subTest(function=name):
                self.assertEqual(kind, "static", f"{name}'s frame has no fixed size")
                self.assertLessEqual(size, BOUND, f"{name}'s frame takes {size} bytes, which marking scans as roots")

    def test_inlined_page_settling_is_detected(self):
        # the negative control: without noinline, pages_settle (and its array of runs) joins collect's frame
        source = (ROOT / "runtime.c").read_text()
        old = "__attribute__((noinline)) static void pages_settle("
        self.assertEqual(source.count(old), 1)
        frames = self.frames(source.replace(old, "static void pages_settle(", 1))
        self.assertGreater(frames["collect"][0], BOUND)


if __name__ == "__main__":
    unittest.main()
