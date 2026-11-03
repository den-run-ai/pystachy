"""Replay seeded random allocations and sweeps against runtime.c's page heap and a model of it.

The probe compiles the page heap from runtime.c (pages_take, pages_give, pages_purge,
pages_settle, zero_dirty and big_new, their helpers, and runtime.c's own Seg, Region and PRun)
with a stand-in for the page map only. Each cycle allocates chunks and large objects, in regions
and in mappings of their own, frees a random subset as a sweep does, and settles with a random
budget. A model of the object on each page checks, after every allocation and every sweep, that
no two live objects share a page; that a zeroed allocation, a chunk taken as clean and a free
page marked clean read zero; that live objects keep their bytes; that the used, dirty and idle
bitmaps, the free runs and the heap count agree with the model; and that the free memory a sweep
keeps fits its budget. Negative controls break the dirty marking of freed pages and the split of
a free run, and expect the probe to fail.
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
"""
STATE = r"""
static Region *regs;
static PRun *bins[2][NBIN];
static I nregs, cregs, nbin[2][NBIN], cbin[2][NBIN];
static Seg *hcache, *bigs;
static I gc_heap, gc_peak, gc_allocd, gc_big;
static _Noreturn void oom(void) { fputs("out of memory\n", stderr); exit(1); }
static void pmap_set(uintptr_t a, uintptr_t e, Seg *s, I bytes) { (void)a; (void)e; (void)s; (void)bytes; }
"""
SUFFIX = r"""
#define MAXR 64                        /* region slots the model follows */
#define MAXO 4096                      /* live objects */
typedef struct { char *p; Seg *s; I n, rg, np; int32_t id; int chunk; unsigned char tag; } Obj;   /* p: its n + 1 bytes */
static Obj obj[MAXO];
static int nobjs;
static int32_t ids, owner[MAXR][RPAGES];   /* the id of the live object on each page; 0: free */
static uint64_t seed;
static uint64_t rnd(void) { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; return seed; }
static I pick(I lo, I hi) { return lo + (I)(rnd() % (uint64_t)(hi - lo + 1)); }
static _Noreturn void bad(const char *why, I a, I b) {
  fprintf(stderr, "%s (%lld, %lld)\n", why, (long long)a, (long long)b);
  exit(1);
}
static int bit(const uint64_t *m, I i) { return m[i >> 6] >> (i & 63) & 1; }
static int zero(const char *p, I n) {
  static const char zeros[65536];
  for (I k = 0; n > 0; p += k, n -= k) {
    k = n < (I)sizeof zeros ? n : (I)sizeof zeros;
    if (memcmp(p, zeros, (size_t)k)) return 0;
  }
  return 1;
}
static void hold(const Obj *x, int set) {   /* the model: x's pages are x's (set) or free */
  if (!x->rg) return;                  /* (a mapping of its own: checked by address) */
  I r = x->rg - 1, first = (I)(((char *)x->s - regs[r].base) / PAGE);
  for (I i = first; i < first + x->np; i++) {
    if (set && owner[r][i]) bad("two live objects share a page", r, i);
    owner[r][i] = set ? x->id : 0;
  }
}
/* every free page of a mapped region in exactly one free run, which holds no used page; after a
   sweep, the runs are whole (a used page or the region's end on each side) and sorted clean or
   dirty by their pages */
static void check_runs(int settled) {
  static int32_t cover[MAXR][RPAGES];
  memset(cover, 0, sizeof cover);
  for (int c = 0; c < 2; c++)
    for (int b = 0; b < NBIN; b++)
      for (I j = 0; j < nbin[c][b]; j++) {
        PRun u = bins[c][b][j];
        if (u.r < 0 || u.r >= nregs || !regs[u.r].base) bad("a free run is in no mapped region", u.r, u.first);
        if (u.n < 1 || u.first < 0 || u.first + u.n > RPAGES) bad("a free run is outside its region", u.first, u.n);
        if (run_bin(u.n) != b) bad("a free run is in the wrong list", u.n, b);
        for (I i = u.first; i < u.first + u.n; i++) {
          if (bit(regs[u.r].used, i) || owner[u.r][i]) bad("a free run covers a used page", u.r, i);
          if (cover[u.r][i]++) bad("a page is in two free runs", u.r, i);
        }
        I d = nbits(regs[u.r].dirty, u.first, u.n);
        if (c == 1 && d) bad("a clean free run holds dirty pages", u.r, u.first);
        if (settled && c == 0 && !d) bad("a dirty free run holds no dirty page", u.r, u.first);
        if (settled && ((u.first > 0 && !bit(regs[u.r].used, u.first - 1)) ||
                        (u.first + u.n < RPAGES && !bit(regs[u.r].used, u.first + u.n))))
          bad("a free run stops short of a used page", u.r, u.first);
      }
  for (I r = 0; r < nregs; r++)
    for (I i = 0; regs[r].base && i < RPAGES; i++)
      if (!bit(regs[r].used, i) && !cover[r][i]) bad("a free page is in no free run", r, i);
}
static void allocate(void) {
  if (nobjs == MAXO) return;
  Obj *x = &obj[nobjs];
  memset(x, 0, sizeof *x);
  x->id = ++ids; x->tag = (unsigned char)(1 + ids % 255);
  int dirty = 1;
  I u = pick(0, 99);
  if (u < 30) {                        /* a chunk (chunk_new) */
    x->p = pages_take(CHUNK / PAGE, &x->rg, &dirty);
    x->s = (Seg *)x->p; x->n = CHUNK - 1; x->np = CHUNK / PAGE; x->chunk = 1;
    if (!dirty && !zero(x->p, CHUNK)) bad("a chunk taken as clean reads nonzero", x->rg, 0);
  } else {                             /* a large object (big_new): scanned, atomic or raw (gc_raw) */
    I np = u < 75 ? pick(3, 16) : u < 91 ? pick(17, 128) : u < 96 ? pick(129, RPAGES) : RPAGES + 128 * pick(1, 4) - pick(0, 31);
    int how = (int)pick(0, 2);
    x->n = np * PAGE - HB - 1 - pick(0, PAGE - 1);
    x->p = big_new(x->n, how == 2 ? 3 : how); bigs = 0;
    x->s = (Seg *)(x->p - HB); x->rg = x->s->rg; x->np = x->s->nobj;
    if ((uintptr_t)x->s % PAGE || x->s->start != x->p || x->s->size != x->n + 1) bad("a large object's header is wrong", x->n, x->np);
    if (how != 2 && !zero(x->p, x->n + 1)) bad("a zeroed allocation reads nonzero", x->rg, x->n);
    if (x->rg ? x->np != np : (x->np < np || x->np - np > np / 4)) bad("a large object holds the wrong number of pages", x->np, np);
  }
  if (x->rg) {
    I r = x->rg - 1;
    if (r >= MAXR) bad("more regions than the model follows", r, 0);
    if (r >= nregs || !regs[r].base || (char *)x->s < regs[r].base || (char *)x->s + x->np * PAGE > regs[r].base + REGION)
      bad("an object is outside its region", r, 0);
    I first = (I)(((char *)x->s - regs[r].base) / PAGE);
    for (I i = first; i < first + x->np; i++) if (!bit(regs[r].used, i)) bad("an allocated page is not marked used", r, i);
  } else {
    for (int o = 0; o < nobjs; o++)
      if (!obj[o].rg && (char *)obj[o].s < (char *)x->s + x->np * PAGE && (char *)x->s < (char *)obj[o].s + obj[o].np * PAGE)
        bad("two live objects share a page", o, 0);
    for (Seg *s = hcache; s; s = s->next) if (s == x->s) bad("a reused mapping is still cached as freed", 0, 0);
  }
  hold(x, 1);
  nobjs++;
  memset(x->p, x->tag, (size_t)(x->n + 1));
}
static void check_all(I keep) {
  I counted = 0, kept = 0, mapped = 0, cached = 0, ncached = 0;
  for (I r = 0; r < nregs; r++) {      /* free pages marked clean read zero: allocations skip clearing them */
    Region *g = &regs[r];
    if (!g->base) {
      for (I i = 0; r < MAXR && i < RPAGES; i++) if (owner[r][i]) bad("a region that holds live objects was unmapped", r, i);
      continue;
    }
    if ((uintptr_t)g->base % REGION) bad("a region is not aligned", r, 0);
    for (I i = 0; i < RPAGES; i++) {
      if (bit(g->used, i) || bit(g->dirty, i)) continue;
      const uint64_t *w = (const uint64_t *)(g->base + i * PAGE);
      for (I k = 0; k < PAGE / 8; k += 64) if (w[k] || w[k + 63]) bad("a free page marked clean reads nonzero", r, i);
    }
  }
  for (int o = 0; o < nobjs; o++) {    /* live objects keep their headers and bytes */
    const Obj *x = &obj[o];
    if (!x->chunk && (x->s->rg != x->rg || x->s->nobj != x->np || x->s->start != x->p)) bad("a live object's header changed", o, x->rg);
    for (char *q = x->p, *e = x->p + x->n + 1; q < e;) {
      char *next = (char *)(((uintptr_t)q + PAGE) & ~(uintptr_t)(PAGE - 1)), *last = (next < e ? next : e) - 1;
      if ((unsigned char)*q != x->tag || (unsigned char)*last != x->tag) bad("a live object lost its bytes", o, q - x->p);
      q = next;
    }
    if (!x->rg) mapped += x->s->nfree;
  }
  for (I r = 0; r < nregs; r++) {      /* the bitmaps and counts */
    Region *g = &regs[r];
    if (!g->base) continue;
    I used = 0;
    for (I i = 0; i < RPAGES; i++) {
      if (bit(g->used, i) != (owner[r][i] != 0)) bad("a page's used bit disagrees with the model", r, i);
      if (bit(g->idle, i) != (bit(g->dirty, i) && !bit(g->used, i))) bad("a page's idle bit is wrong after the sweep", r, i);
      used += bit(g->used, i);
      counted += bit(g->used, i) || bit(g->dirty, i);
      kept += bit(g->dirty, i) && !bit(g->used, i);
    }
    if (used != g->nused) bad("a region's used pages are miscounted", r, g->nused);
  }
  for (Seg *s = hcache; s; s = s->next) {   /* freed mappings kept for reuse */
    for (int o = 0; o < nobjs; o++) if (obj[o].s == s) bad("a live object's mapping is cached as freed", o, 0);
    if (s->rg || (uintptr_t)s % REGION || ++ncached > MAXO) bad("the cache of freed mappings is corrupt", ncached, 0);
    cached += s->nfree;
  }
  if (gc_heap != counted * PAGE + mapped + cached) bad("the heap count disagrees with the pages held", gc_heap, counted * PAGE + mapped + cached);
  if (os_page() == PAGE && kept * PAGE + cached > keep) bad("a sweep kept more free memory than its budget", kept * PAGE + cached, keep);
  check_runs(1);
}
static void sweep_settle(I keep, int all) {   /* sweep's freeing of chunks and large objects, then pages_settle */
  Seg *freed = 0;
  I held = 0;
  for (int o = 0; o < nobjs; o++) held += obj[o].np;
  I p = all ? 100 : held > 6000 ? 80 : pick(10, 60);
  for (int o = nobjs - 1; o >= 0; o--) {
    if (pick(0, 99) >= p) continue;
    Obj *x = &obj[o];
    hold(x, 0);
    if (x->rg) pages_give(x->rg, (uintptr_t)x->s, x->np);
    else { x->s->next = freed; freed = x->s; }
    obj[o] = obj[--nobjs];
  }
  pages_settle(freed, keep);
  check_all(keep);
}
int main(int argc, char **argv) {
  if (argc != 3) bad("arguments: seed cycles", argc, 0);
  seed = strtoull(argv[1], 0, 10) * 0x9E3779B97F4A7C15ULL | 1;
  I cycles = atoll(argv[2]);
  for (I c = 0; c < cycles; c++) {
    for (I k = pick(1, 24); k > 0; k--) { allocate(); check_runs(0); }
    I u = pick(0, 3), keep = u == 0 ? 0 : u == 1 ? pick(0, 4 << 20) : u == 2 ? pick(4 << 20, 16 << 20) : (I)1 << 30;
    sweep_settle(keep, 0);
  }
  sweep_settle(0, 1);                  /* everything freed, nothing kept */
  if (gc_heap || hcache || nobjs) bad("memory is still counted after everything was freed", gc_heap, nobjs);
  printf("page heap model passed: %lld cycles, %d objects\n", (long long)cycles, ids);
  return 0;
}
"""
DEFINES = ["PAGE", "CHUNK", "REGION", "RPAGES", "NBIN"]
HELPERS = ["os_page", "heap_add", "map_pages", "purge", "bits", "nbits", "next_bit", "run_bin", "run_push",
           "pages_take", "pages_give", "pages_purge", "zero_dirty", "pages_settle", "big_new"]


def function(source, name):
    match = re.search(r"^(?:__attribute__\(\([a-z_, ]*\)\) )?static [A-Za-z_]+ \*?" + name + r"\([^\n]*\) \{(?:[^\n]*\}$|.*?^\})",
                      source, re.M | re.S)
    if match is None:
        raise AssertionError(f"missing runtime function: {name}")
    return match[0] + "\n"


def probe_source(runtime):
    parts = [PREFIX]
    for name in DEFINES:
        match = re.search(r"^#define " + name + r" [^\n]*\n", runtime, re.M)
        if match is None:
            raise AssertionError(f"missing runtime definition: {name}")
        parts.append(match[0])
    for pattern in (r"^typedef uintptr_t __attribute__\(\(may_alias\)\) W;[^\n]*\n",
                    r"^typedef struct Seg Seg;\n.*?^#define HB [^\n]*\n"):   # Seg, Region, PRun and HB
        match = re.search(pattern, runtime, re.M | re.S)
        if match is None:
            raise AssertionError(f"missing runtime definitions: {pattern}")
        parts.append(match[0])
    parts.append(STATE)
    parts.extend(function(runtime, name) for name in HELPERS)
    return "".join(parts) + SUFFIX


@unittest.skipUnless(CLANG, "clang is required for the page heap's model test")
class RuntimePageHeap(unittest.TestCase):
    def build(self, directory, source):
        path = Path(directory) / "pageheap"
        result = subprocess.run([CLANG, "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c", "-", "-o", str(path)],
                                input=source, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def replay(self, source, seeds, cycles):
        with tempfile.TemporaryDirectory() as directory:
            executable = self.build(directory, source)
            return [subprocess.run([str(executable), str(seed), str(cycles)], capture_output=True, text=True, timeout=120)
                    for seed in seeds]

    def test_random_cycles_agree_with_the_model(self):
        for seed, result in zip((1, 2, 3), self.replay(probe_source((ROOT / "runtime.c").read_text()), (1, 2, 3), 120)):
            with self.subTest(seed=seed):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(result.stdout, r"^page heap model passed: 120 cycles, \d+ objects\n$")

    def mutated(self, old, new):
        source = probe_source((ROOT / "runtime.c").read_text())
        self.assertEqual(source.count(old), 1)
        return source.replace(old, new, 1)

    def test_freed_pages_left_clean_are_detected(self):
        # the negative control: pages_give that does not mark the freed pages dirty lets a later
        # zeroed allocation, or a page that the sweep keeps, hand out an old object's bytes as zero
        source = self.mutated("bits(g->used, first, np, 0); bits(g->dirty, first, np, 1); g->nused -= np;",
                              "bits(g->used, first, np, 0); g->nused -= np;")
        result = self.replay(source, (1,), 120)[0]
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reads nonzero", result.stderr)

    def test_a_split_run_that_overlaps_its_allocation_is_detected(self):
        # the negative control: pages_take that gives back the rest of a run from its last taken
        # page hands that page out twice
        source = self.mutated("if (u.n > np) run_push(c, u.r, u.first + np, u.n - np);",
                              "if (u.n > np) run_push(c, u.r, u.first + np - 1, u.n - np + 1);")
        result = self.replay(source, (1,), 120)[0]
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("a free run covers a used page", result.stderr)


if __name__ == "__main__":
    unittest.main()
