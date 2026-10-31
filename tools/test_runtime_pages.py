"""Exercise the real string trim with simulated 4/16/64 KiB kernel pages.

The probe compiles str_trim and its page-discard helper from runtime.c. It
substitutes only the OS calls and page-map update, so a 4 KiB development host
can detect a discard that would damage a neighbouring allocation on ARM64.
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
PREFIX = r"""
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
typedef int64_t I;
typedef struct { I len; uint64_t dict_hash; I chars1; char s[]; } Str;
typedef struct { char *start; I size, lim, nlive; } Seg;
#define PAGE 4096
static long kernel_page;
static unsigned calls;
static uintptr_t live_end, allocation_end, advised_start, advised_end;
static _Noreturn void bad(const char *why) { fprintf(stderr, "%s\n", why); exit(1); }
long probe_sysconf(int name) {
  if (name != _SC_PAGESIZE) bad("unexpected sysconf query");
  return kernel_page;
}
int probe_madvise(void *address, size_t length, int advice) {
  uintptr_t a = (uintptr_t)address;
  if (advice != MADV_DONTNEED) bad("unexpected advice");
  if (kernel_page <= 0 || (kernel_page & (kernel_page - 1))) bad("discard with unknown page size");
  if (a % kernel_page) bad("discard start is not a kernel page boundary");
  /* Model the kernel's upward length rounding before checking containment. */
  uintptr_t end = a + ((length + kernel_page - 1) / kernel_page) * kernel_page;
  if (a < live_end || end > allocation_end) bad("discard extends beyond the unused allocation tail");
  if (!length || length % kernel_page) bad("discard length is not whole kernel pages");
  memset(address, 0, end - a);
  advised_start = a; advised_end = end; calls++;
  return 0;
}
static void pmap_set(uintptr_t a, uintptr_t e, Seg *seg, I bytes) {
  (void)bytes;
  if (seg || a % PAGE || a < live_end || e != allocation_end) bad("page-map trim changed");
}
#define sysconf probe_sysconf
#define madvise probe_madvise
"""
SUFFIX = r"""
static void exercise(size_t offset, I capacity, I kept, int expect_discard) {
  const size_t total = 8 * 65536;
  void *storage = NULL;
  if (posix_memalign(&storage, 65536, total)) bad("probe allocation failed");
  memset(storage, 0xA5, total);
  Str *text = (Str *)((char *)storage + 65536 + offset);
  text->len = kept - (I)sizeof(Str) - 1;
  Seg seg = {(char *)text, capacity + 1, capacity + 1, text->len + 1};
  live_end = (uintptr_t)text + kept + 1;
  allocation_end = (uintptr_t)text + capacity + 1;
  calls = 0; advised_start = advised_end = 0;
  str_trim(&seg);
  if (seg.size != kept + 1 || seg.lim != kept + 1) bad("logical trim did not run");
  if (calls != (unsigned)expect_discard) bad("whole unused pages were not released as expected");
  for (uintptr_t p = (uintptr_t)text + sizeof(Str); p < live_end; p++)
    if (*(unsigned char *)p != 0xA5) bad("live string or slack byte discarded");
  for (uintptr_t p = allocation_end; p < (uintptr_t)storage + total; p++)
    if (*(unsigned char *)p != 0xA5) bad("neighbouring allocation discarded");
  for (uintptr_t p = advised_start; p < advised_end; p++)
    if (*(unsigned char *)p != 0) bad("eligible unused page not discarded");
  free(storage);
}
int main(int argc, char **argv) {
  if (argc != 2) bad("page size argument required");
  kernel_page = strtol(argv[1], NULL, 10);
  int valid = kernel_page == 4096 || kernel_page == 16384 || kernel_page == 65536;
  /* The first old 4 KiB range starts on a 64 KiB boundary but ends partway
     through a page: Linux would round it into a neighbouring allocation. */
  exercise(0, 3 * 65536 + 6143, 65536 - 4096, valid);
  exercise(123, 3 * 65536 + 6143, 65536 - 4096, valid);
  exercise(0, 8191, 3072, kernel_page == 4096);
  exercise(100, 7000, 512, 0);
  puts("page discard containment and release passed");
  return 0;
}
"""


def function(source, name):
    match = re.search(r"^static void " + name + r"\([^\n]*\) \{.*?^\}", source, re.M | re.S)
    if match is None:
        raise AssertionError(f"missing runtime function: {name}")
    return match[0] + "\n"


@unittest.skipUnless(CLANG, "clang is required for the runtime page-size controls")
class RuntimePages(unittest.TestCase):
    def compile(self, directory, source, name):
        path = Path(directory) / name
        result = subprocess.run([CLANG, "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c", "-", "-o", str(path)],
                                input=PREFIX + source + SUFFIX, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def test_real_trim_preserves_neighbours_and_releases_whole_pages(self):
        runtime = (ROOT / "runtime.c").read_text()
        helper = function(runtime, "discard_pages") if "static void discard_pages(" in runtime else ""
        source = helper + function(runtime, "str_trim")
        with tempfile.TemporaryDirectory() as directory:
            executable = self.compile(directory, source, "pages")
            for size in (4096, 16384, 65536, -1, 0, 3, 6000):
                with self.subTest(page_size=size):
                    result = subprocess.run([str(executable), str(size)], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "page discard containment and release passed\n")

    def test_original_collector_page_alignment_is_detected(self):
        runtime = (ROOT / "runtime.c").read_text()
        old = "if (a < (e & ~(uintptr_t)(PAGE - 1))) madvise((void *)a, (e & ~(uintptr_t)(PAGE - 1)) - a, MADV_DONTNEED);"
        source = function(runtime, "str_trim").replace("discard_pages(a, e);", old)
        with tempfile.TemporaryDirectory() as directory:
            executable = self.compile(directory, source, "old-pages")
            good = subprocess.run([str(executable), "4096"], capture_output=True, text=True, timeout=10)
            self.assertEqual(good.returncode, 0, good.stderr)
            bad = subprocess.run([str(executable), "65536"], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("discard extends beyond the unused allocation tail", bad.stderr)


if __name__ == "__main__":
    unittest.main()
