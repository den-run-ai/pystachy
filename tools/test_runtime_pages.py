"""Exercise the real string trim with simulated 4/16/64 KiB kernel pages.

The probe compiles str_trim and the page heap's helpers that it calls (pages_give,
pages_purge, purge, os_page and the bitmap helpers) from runtime.c. It substitutes
only the OS calls and the page-map update, so a 4 KiB development host can detect a
purge that would damage a neighbouring allocation on ARM64: one in the same region,
and one past a large object's own mapping.
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
typedef struct { char *start; I size, nobj, lim, nfree, nlive, rg; } Seg;
#define PAGE 4096
#define REGION ((I)2 << 20)
#define RPAGES ((int)(REGION / PAGE))
#define HB 128
typedef struct { char *base; uint64_t used[RPAGES / 64], dirty[RPAGES / 64], idle[RPAGES / 64]; I nused; } Region;
static Region region, *regs = &region;
static I gc_heap, gc_peak;
static long kernel_page;
static unsigned calls;
static uintptr_t live_end, allocation_end, advised_start, advised_end, map_start, map_end;
static _Noreturn void bad(const char *why) { fprintf(stderr, "%s\n", why); exit(1); }
__attribute__((unused)) static _Noreturn void oom(void) { bad("out of memory"); }
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
  if (calls) bad("more than one discard");
  memset(address, 0, end - a);
  advised_start = a; advised_end = end; calls++;
  return 0;
}
static void pmap_set(uintptr_t a, uintptr_t e, Seg *seg, I bytes) {
  (void)bytes;
  if (seg || a % PAGE || a < live_end || e != map_end || a != map_start) bad("page-map trim changed");
}
#define sysconf probe_sysconf
#define madvise probe_madvise
"""
SUFFIX = r"""
static int bit(const uint64_t *m, I i) { return m[i >> 6] >> (i & 63) & 1; }
/* A str of capacity bytes (header and slack included) in a large object at page `at` of a region or
   (own) of a mapping of its own, followed by a neighbour's pages; trimmed to kept bytes */
static void exercise(int own, I at, I capacity, I kept, int expect_discard) {
  const size_t total = (size_t)REGION;
  void *storage = NULL;
  if (posix_memalign(&storage, (size_t)REGION, total)) bad("probe allocation failed");
  memset(storage, 0xA5, total);
  memset(&region, 0, sizeof region);
  region.base = storage;
  Seg *s = (Seg *)((char *)storage + at * PAGE);
  Str *text = (Str *)((char *)s + HB);
  I np = (HB + capacity + 1 + PAGE - 1) / PAGE;
  text->len = kept - (I)sizeof(Str) - 1;
  *s = (Seg){(char *)text, capacity + 1, np, capacity + 1, own ? np * PAGE : 0, text->len + 1, own ? 0 : 1};
  bits(region.used, 0, RPAGES, 1); bits(region.dirty, 0, RPAGES, 1); region.nused = RPAGES;
  live_end = (uintptr_t)text + kept + 1;
  allocation_end = (uintptr_t)s + np * PAGE;
  map_start = ((uintptr_t)text + kept + PAGE) & ~(uintptr_t)(PAGE - 1); map_end = (uintptr_t)text + capacity + 1;
  calls = 0; advised_start = advised_end = 0; gc_heap = 0;
  str_trim(s);
  if (s->size != kept + 1 || s->lim != kept + 1) bad("logical trim did not run");
  if (calls != (unsigned)expect_discard) bad("whole unused pages were not released as expected");
  for (uintptr_t p = (uintptr_t)text + sizeof(Str); p < live_end; p++)
    if (*(unsigned char *)p != 0xA5) bad("live string or slack byte discarded");
  for (uintptr_t p = (uintptr_t)storage; p < (uintptr_t)storage + total; p++)
    if ((p < advised_start || p >= advised_end) && p >= live_end && *(unsigned char *)p != 0xA5) bad("neighbouring allocation discarded");
  for (uintptr_t p = advised_start; p < advised_end; p++)
    if (*(unsigned char *)p != 0) bad("eligible unused page not discarded");
  I keep = (I)((map_start - (uintptr_t)s) / PAGE);
  if (gc_heap != -(I)(advised_end - advised_start)) bad("the heap does not count the discarded pages out");
  if (own) {
    if (s->nobj != np || s->nfree != np * PAGE - (I)(advised_end - advised_start)) bad("own mapping's pages or counted bytes changed");
  } else {
    if (s->nobj != keep) bad("the str's run did not shrink to its pages");
    for (I i = 0; i < RPAGES; i++) {
      uintptr_t p = (uintptr_t)storage + i * PAGE;
      int tail = i >= at + keep && i < at + np, clean = p >= advised_start && p < advised_end;
      if (bit(region.used, i) == tail) bad("a page's use is wrong after the trim");
      if (bit(region.dirty, i) == clean) bad("a page's dirty bit is wrong after the trim");
    }
    if (region.nused != RPAGES - (np - keep)) bad("the region's used pages are miscounted");
  }
  free(storage);
}
int main(int argc, char **argv) {
  if (argc != 2) bad("page size argument required");
  kernel_page = strtol(argv[1], NULL, 10);
  int valid = kernel_page == 4096 || kernel_page == 16384 || kernel_page == 65536;
  for (int own = 0; own < 2; own++) {
    /* The run starts on a 64 KiB boundary but its tail ends partway through a 64 KiB page, beside a
       neighbour: purging up to the 4 KiB page past the str would round into that neighbour */
    exercise(own, 16, 3 * 65536 + 6143, 65536 - 4096, valid);
    exercise(own, 17, 3 * 65536 + 6143, 65536 - 4096, valid);
    exercise(own, 32, 8191 + 2 * 65536, 3072, valid);
    exercise(own, 3, 8191, 3072, kernel_page == 4096);
    exercise(own, 40, 7000, 512, kernel_page == 4096);
    exercise(own, 44, 3000, 500, 0);   /* the str's one page: nothing to give back */
  }
  puts("page discard containment and release passed");
  return 0;
}
"""
HELPERS = ["os_page", "heap_add", "purge", "bits", "nbits", "pages_give", "pages_purge", "str_trim"]


def function(source, name):
    match = re.search(r"^static [A-Za-z_]+ \*?" + name + r"\([^\n]*\) \{(?:[^\n]*\}$|.*?^\})", source, re.M | re.S)
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
        source = "".join(function(runtime, name) for name in HELPERS)
        with tempfile.TemporaryDirectory() as directory:
            executable = self.compile(directory, source, "pages")
            for size in (4096, 16384, 65536, -1, 0, 3, 6000):
                with self.subTest(page_size=size):
                    result = subprocess.run([str(executable), str(size)], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "page discard containment and release passed\n")

    def test_collector_page_rounding_is_detected(self):
        # the negative control: a purge that rounds to the collector's 4 KiB pages instead of the
        # kernel's discards part of a neighbour where a kernel page is 64 KiB
        runtime = (ROOT / "runtime.c").read_text()
        source = "".join(function(runtime, name) for name in HELPERS)
        old = "  I page = os_page();\n  if (!page) return 0;\n"
        self.assertEqual(source.count(old), 1)
        source = source.replace(old, "  I page = os_page() ? PAGE : 0;\n  if (!page) return 0;\n", 1)
        with tempfile.TemporaryDirectory() as directory:
            executable = self.compile(directory, source, "old-pages")
            good = subprocess.run([str(executable), "4096"], capture_output=True, text=True, timeout=10)
            self.assertEqual(good.returncode, 0, good.stderr)
            bad = subprocess.run([str(executable), "65536"], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("discard", bad.stderr)


if __name__ == "__main__":
    unittest.main()
