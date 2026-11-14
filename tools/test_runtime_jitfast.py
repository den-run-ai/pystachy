"""Check the JIT tier's allocation fast path against runtime.c's own.

lower_module.py's JITFAST copies gc_alloc's fast path into each program that the JIT tier runs, as LLVM
IR: the 136-byte cutoff, the size class's free list in pys_fl, the complemented links and the slow
call. The test compiles the module that lower_module.jit_alloc makes of a small program (JITFAST in place
of pys_alloc's and pys_new's declarations) beside a harness built from runtime.c's own gc_alloc,
cls() and size classes. For every size up to 300 bytes, with full and with empty free lists, it
checks that gc_alloc pops cls()'s list, whose slots have room for the size, and that below 136
bytes JITFAST returns the slot gc_alloc returns or calls the slow path with the same size and
kind, and leaves the same lists behind. From 136 bytes gc_alloc pops a list too, which the JIT
tier does not copy: there JITFAST must call the slow path, which takes the slot itself, and
leave the lists alone. It also checks that jit_alloc declares pys_gc_slow once when the program
declares it already. The negative control shifts JITFAST's class by one and expects the
comparison to fail.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler import lower_module  # noqa: E402

CLANG = shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang")
PROGRAM = """declare ptr @pys_alloc(i64)
declare ptr @pys_new(i64)

define ptr @probe_alloc(i64 %n) {
  %p = call ptr @pys_alloc(i64 %n)
  ret ptr %p
}

define ptr @probe_new(i64 %n) {
  %p = call ptr @pys_new(i64 %n)
  ret ptr %p
}
"""
PREFIX = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int64_t I;
"""
STATE = r"""
W *pys_fl[NK];
static W slow;                         /* the slow path's slot */
static I slow_n, slow_how;
static void *gc_slow(I n, int how) { slow_n = n; slow_how = how; return &slow; }
void *pys_gc_slow(I n, I how) { slow_n = n; slow_how = how; return &slow; }
"""
SUFFIX = r"""
void *probe_alloc(I n);                /* JITFAST's pys_alloc and pys_new, through the program */
void *probe_new(I n);
static W cells[NK][2];
static void lists(int full) {          /* each free list two slots long, or empty */
  for (int k = 0; k < NK; k++) {
    cells[k][0] = ~(uintptr_t)&cells[k][1]; cells[k][1] = ~(uintptr_t)0;
    pys_fl[k] = full ? &cells[k][0] : 0;
  }
  slow_n = slow_how = -1;
}
static _Noreturn void bad(const char *name, const char *why, I n, int full) {
  printf("%s %s: %lld bytes, %s free lists\n", name, why, (long long)n, full ? "full" : "empty");
  exit(1);
}
int main(void) {
  void *(*jit[2])(I) = {probe_alloc, probe_new};
  const char *name[2] = {"pys_alloc's JIT fast path", "pys_new's JIT fast path"};
  static W *lists_after[NK], cells_after[NK][2];
  for (int full = 0; full < 2; full++)
    for (I n = 0; n <= 300; n++)
      for (int f = 0; f < 2; f++) {
        lists(full);
        void *want = gc_alloc(n, 0);
        I want_n = slow_n, want_how = slow_how;
        memcpy(lists_after, pys_fl, sizeof lists_after); memcpy(cells_after, cells, sizeof cells_after);
        if (full) {                    /* gc_alloc pops cls()'s list, whose slots hold n bytes and the slack byte */
          I k = (W *)want - &cells[0][0];
          if (k < 0 || k % 2 || k / 2 >= NK || k / 2 != 2 * cls(n) || csize[cls(n)] < n + 1) bad("gc_alloc", "pops a list without room", n, full);
        } else if (want != &slow || want_n != n || want_how != 0) bad("gc_alloc", "does not call the slow path for an empty list", n, full);
        if (n >= 136) {                /* the JIT tier's copy ends here: the slow path, and the lists as they were */
          lists(full);
          want = &slow; want_n = n; want_how = 0;
          memcpy(lists_after, pys_fl, sizeof lists_after); memcpy(cells_after, cells, sizeof cells_after);
        }
        lists(full);
        void *got = jit[f](n);
        if (got != want) bad(name[f], "returns another slot than gc_alloc", n, full);
        if (slow_n != want_n || slow_how != want_how) bad(name[f], "calls the slow path otherwise than gc_alloc", n, full);
        if (memcmp(lists_after, pys_fl, sizeof lists_after) || memcmp(cells_after, cells, sizeof cells_after))
          bad(name[f], "leaves the free lists otherwise than gc_alloc", n, full);
      }
  puts("the JIT fast path agrees with gc_alloc");
  return 0;
}
"""


def runtime_part(source, pattern):
    match = re.search(pattern, source, re.M | re.S)
    if match is None:
        raise AssertionError(f"missing runtime definition: {pattern}")
    return match[0]


def harness():
    runtime = (ROOT / "runtime.c").read_text()
    return (PREFIX
            # JITFAST is compared with the default, uninstrumented allocator.
            + runtime_part(runtime, r"^#define PROFILE_ALLOC\(n\) \(\(void\)0\)\n")
            + runtime_part(runtime, r"^typedef uintptr_t __attribute__\(\(may_alias\)\) W;[^\n]*\n")
            + runtime_part(runtime, r"^#define SMALL [^\n]*\n")
            + runtime_part(runtime, r"^#define NK [^\n]*\n")
            + runtime_part(runtime, r"^static const short csize\[NK / 2\] = \{.*?\};\n")
            + runtime_part(runtime, r"^static I cls\(I n\) \{.*?^\}\n")
            + STATE
            + runtime_part(runtime, r"^static inline __attribute__\(\(always_inline\)\) void \*gc_alloc\(I n, int atomic\) \{.*?^\}\n")
            + SUFFIX)


@unittest.skipUnless(CLANG, "clang is required for the JIT fast path's check")
class RuntimeJitFast(unittest.TestCase):
    def compare(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            (temp / "harness.c").write_text(harness())
            (temp / "program.ll").write_text(lower_module.jit_alloc(PROGRAM))
            build = subprocess.run([CLANG, "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c", str(temp / "harness.c"),
                                    "-x", "ir", str(temp / "program.ll"), "-Wno-override-module", "-o", str(temp / "probe")],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(build.returncode, 0, build.stderr)
            return subprocess.run([str(temp / "probe")], capture_output=True, text=True, timeout=60)

    def test_jit_fast_path_agrees_with_gc_alloc(self):
        result = self.compare()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "the JIT fast path agrees with gc_alloc\n")

    def test_a_shifted_size_class_is_detected(self):
        # the negative control: JITFAST computing the class one too high pops another class's list
        old = "  %e = add i64 %d, -4\n"
        self.assertEqual(lower_module.JITFAST.count(old), 1)
        with patch.object(lower_module, "JITFAST", lower_module.JITFAST.replace(old, "  %e = add i64 %d, -2\n")):
            result = self.compare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("returns another slot than gc_alloc", result.stdout)

    def test_a_program_that_declares_the_slow_path_keeps_one_declaration(self):
        ir = lower_module.jit_alloc(PROGRAM + "declare ptr @pys_gc_slow(i64, i64)\n")
        self.assertEqual(ir.count("declare ptr @pys_gc_slow("), 1)
        self.assertEqual(ir.count("@pys_fl = "), 1)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([CLANG, "-c", "-x", "ir", "-", "-Wno-override-module", "-o", str(Path(directory) / "program.o")],
                                    input=ir, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
