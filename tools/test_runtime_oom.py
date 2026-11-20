"""A collection that runs out of memory ends the program with MemoryError and status 1 (#1585).

oom() runs pys_finish(), and so atexit's callbacks, which may allocate. A failed mark-stack
growth used to leave the stack's pointer null and its capacity grown, so the collection that a
callback started wrote through it and the program died of SIGSEGV. An LD_PRELOAD shim fails the
mark stack's first realloc(), of 32,768 bytes, in a collection that the program's own
allocations start; its atexit callback then allocates past the first collection's threshold.
The program must print MemoryError, run the callback and exit with status 1. Without the shim,
the same executable runs to its end and the callback, with status 0.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LLVM = os.environ.get("PYSTACHY_LLVM", "")
CLANG = shutil.which(str(Path(LLVM) / "clang") if LLVM else "clang")
HAVE_LLVM = all(shutil.which(str(Path(LLVM) / tool) if LLVM else tool)
                for tool in ("clang", "opt", "lli", "llvm-link", "llvm-as"))

# the mark stack's first growth: realloc(NULL, 4096 entries of 8 bytes) (runtime.c's mstk_grow)
SHIM = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stddef.h>
static int failed;
void *realloc(void *p, size_t n) {
  static void *(*real)(void *, size_t);
  if (!real) real = (void *(*)(void *, size_t))dlsym(RTLD_NEXT, "realloc");
  if (!p && n == 32768 && !failed) { failed = 1; return NULL; }
  return real(p, n);
}
"""

PROGRAM = """import atexit


def late() -> None:
    n = 0
    for i in range(2000000):
        n += len(str(i))
    print("callback allocated", n)


atexit.register(late)
held: list[str] = []
for i in range(2000000):
    held.append(str(i))
print("main done", len(held))
"""


@unittest.skipUnless(sys.platform == "linux", "LD_PRELOAD and glibc's dlsym(RTLD_NEXT)")
@unittest.skipUnless(HAVE_LLVM and CLANG, "requires clang, opt, lli, llvm-link and llvm-as")
class OomInCollectionTests(unittest.TestCase):
    def test_failed_mark_stack_growth_exits_with_memory_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "shim.c").write_text(SHIM)
            subprocess.run([CLANG, "-shared", "-fPIC", "-O1", str(root / "shim.c"), "-o", str(root / "shim.so"), "-ldl"],
                           check=True, capture_output=True, text=True)
            (root / "program.py").write_text(PROGRAM)
            executable = root / "program"
            build = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "build", str(root / "program.py"),
                                    "-o", str(executable)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith("PYSTACHY_GC") and key != "LD_PRELOAD"}

            plain = subprocess.run([str(executable)], env=environment, capture_output=True, text=True, timeout=120)
            self.assertEqual((plain.returncode, plain.stdout), (0, "main done 2000000\ncallback allocated 12888890\n"),
                             plain.stderr)

            failing = subprocess.run([str(executable)], env={**environment, "LD_PRELOAD": str(root / "shim.so")},
                                     capture_output=True, text=True, timeout=120)
            self.assertEqual(failing.returncode, 1, f"stdout: {failing.stdout!r}, stderr: {failing.stderr!r}")
            self.assertEqual(failing.stderr, "MemoryError\n")
            self.assertEqual(failing.stdout, "callback allocated 12888890\n")


if __name__ == "__main__":
    unittest.main()
