"""Write an untimed graph-counter runtime overlay from a pinned runtime.c.

Usage: python instrument_runtime.py INPUT_RUNTIME OUTPUT_RUNTIME
Counters are cumulative. dynany_bench.py calls process_time_ns three times:
subtract snapshots 1-0 for construction and 2-1 for processing. No timers or
benchmarks should use this instrumented runtime as performance evidence.
"""
from pathlib import Path
import sys


source = Path(sys.argv[1]).read_text()


def replace(old: str, new: str) -> None:
    global source
    assert source.count(old) == 1, (old, source.count(old))
    source = source.replace(old, new)


replace("typedef int64_t I;", """typedef int64_t I;
/* Temporary graph-copy diagnostic counters; never a timing build. */
static uint64_t mp_int_calls, mp_int_allocs, mp_ref_calls, mp_keyeqs;
static uint64_t mp_lookups[5], mp_probes[5], mp_hash_matches[5];
static unsigned mp_snapshots;
static void mp_snapshot(void) {
  fprintf(stderr, "MEMO_PROFILE snapshot=%u int_calls=%llu int_allocs=%llu ref_calls=%llu keyeqs=%llu",
          mp_snapshots++, (unsigned long long)mp_int_calls, (unsigned long long)mp_int_allocs,
          (unsigned long long)mp_ref_calls, (unsigned long long)mp_keyeqs);
  for (int j = 0; j < 5; j++) fprintf(stderr, " cat%d=%llu,%llu,%llu", j,
          (unsigned long long)mp_lookups[j], (unsigned long long)mp_probes[j],
          (unsigned long long)mp_hash_matches[j]);
  fputc('\\n', stderr);
}
""")
replace("static I dfindc(Dict *d, I k, uint64_t h, I *free);", """/* Categories: raw-int, raw-str, Any-int-query, Any-other-query, other typed key. */
static int mp_category(Dict *d, I k) {
  if (!d->kind) return 0;
  if (d->kind == 1) return 1;
  const char *s = kdesc(d->kind);
  if (*s == 'A' && !s[1]) return ((Dyn *)k)->t->kind == 2 ? 2 : 3;
  return 4;
}
static I dfindc(Dict *d, I k, uint64_t h, I *free);""")
replace("  I f = -1; int ran = 0;\n  for (uint64_t i = h & m, p = h;; p >>= 5, i = (i * 5 + p + 1) & m) {\n    DICT_PROBE();", """  I f = -1; int ran = 0;
  int mp_cat = mp_category(d, k);
  for (uint64_t i = h & m, p = h;; p >>= 5, i = (i * 5 + p + 1) & m) {
    mp_probes[mp_cat]++;
    DICT_PROBE();""")
replace("    else if (d->hs[e - 1] == h) {\n      I x = d->keys[e - 1];", """    else if (d->hs[e - 1] == h) {
      mp_hash_matches[mp_cat]++;
      I x = d->keys[e - 1];""")
replace("static inline __attribute__((always_inline)) I dhfind(Dict *d, I k, uint64_t *hp, I *free) {", """static inline __attribute__((always_inline)) I dhfind(Dict *d, I k, uint64_t *hp, I *free) {
  mp_lookups[mp_category(d, k)]++;""")
replace("  DICT_KEYEQ();", "  mp_keyeqs++;\n  DICT_KEYEQ();")
replace("Dyn *pys_dyn_int(I v) {", "Dyn *pys_dyn_int(I v) {\n  mp_int_calls++;")
replace("  Dyn *d = gc_box(1); d->t = &pys_dyntype_int; d->v = v; return d;", "  mp_int_allocs++;\n  Dyn *d = gc_box(1); d->t = &pys_dyntype_int; d->v = v; return d;")
replace("Dyn *pys_dyn_ref(const DynType *t, void *p) {", "Dyn *pys_dyn_ref(const DynType *t, void *p) {\n  mp_ref_calls++;")
replace("I pys_process_time_ns(void) { return clock_ns(CLOCK_PROCESS_CPUTIME_ID); }", "I pys_process_time_ns(void) { mp_snapshot(); return clock_ns(CLOCK_PROCESS_CPUTIME_ID); }")
Path(sys.argv[2]).write_text(source)
