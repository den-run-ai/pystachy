"""Write an untimed graph-counter runtime overlay from a pinned runtime.c.

Usage: python instrument_graph_nobox.py INPUT_RUNTIME OUTPUT_RUNTIME
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
static uint64_t mp_int_calls, mp_int_allocs, mp_ref_calls, mp_keyeqs, mp_slots_total;
static uint64_t mp_nobox_calls, mp_nobox_probes, mp_nobox_hits, mp_nobox_misses, mp_nobox_fallbacks;
static uint64_t mp_lookups[5], mp_probes[5], mp_hash_matches[5];
static unsigned mp_snapshots;
static void mp_snapshot(void) {
  fprintf(stderr, "MEMO_PROFILE snapshot=%u int_calls=%llu int_allocs=%llu ref_calls=%llu keyeqs=%llu slots_total=%llu"
          " nobox_calls=%llu nobox_probes=%llu nobox_hits=%llu nobox_misses=%llu nobox_fallbacks=%llu",
          mp_snapshots++, (unsigned long long)mp_int_calls, (unsigned long long)mp_int_allocs,
          (unsigned long long)mp_ref_calls, (unsigned long long)mp_keyeqs, (unsigned long long)mp_slots_total,
          (unsigned long long)mp_nobox_calls, (unsigned long long)mp_nobox_probes,
          (unsigned long long)mp_nobox_hits, (unsigned long long)mp_nobox_misses,
          (unsigned long long)mp_nobox_fallbacks);
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
replace("#define DICT_PROBE()", "#define DICT_PROBE() (mp_slots_total++)")
replace("Dyn *pys_dyn_int(I v) {", "Dyn *pys_dyn_int(I v) {\n  mp_int_calls++;")
replace("  Dyn *d = gc_box(1); d->t = &pys_dyntype_int; d->v = v; return d;", "  mp_int_allocs++;\n  Dyn *d = gc_box(1); d->t = &pys_dyntype_int; d->v = v; return d;")
replace("Dyn *pys_dyn_ref(const DynType *t, void *p) {", "Dyn *pys_dyn_ref(const DynType *t, void *p) {\n  mp_ref_calls++;")
replace("I pys_process_time_ns(void) { return clock_ns(CLOCK_PROCESS_CPUTIME_ID); }", "I pys_process_time_ns(void) { mp_snapshot(); return clock_ns(CLOCK_PROCESS_CPUTIME_ID); }")

# The new helper bypasses dhfind/dlook, so account for it explicitly. Category 2
# combines boxed integer operations with these pure integer operations; separate
# nobox fields retain the path split. slots_total also counts rebuild/insert slots.
marker = "LOOKUP I pys_dict_find_int_nobox(Dict *d, I value) {"
if marker in source:
    start = source.index(marker)
    end = source.index("\n}\n", start) + 3
    body = source[start:end]
    def edit(old: str, new: str) -> None:
        global body
        assert body.count(old) == 1, (old, body.count(old))
        body = body.replace(old, new)
    edit(marker, marker + "\n  mp_nobox_calls++; mp_lookups[2]++;")
    edit("  if (!d->size) return -1;", "  if (!d->size) { mp_nobox_misses++; return -1; }")
    edit("    DICT_PROBE();", "    mp_nobox_probes++; mp_probes[2]++;\n    DICT_PROBE();")
    edit("    if (!e) return -1;", "    if (!e) { mp_nobox_misses++; return -1; }")
    edit("    if (e > 0 && d->hs[e - 1] == h) {", "    if (e > 0 && d->hs[e - 1] == h) {\n      mp_hash_matches[2]++;")
    edit("      if (key->t != &pys_dyntype_int && key->t != &pys_dyntype_bool) return -2;",
         "      if (key->t != &pys_dyntype_int && key->t != &pys_dyntype_bool) { mp_nobox_fallbacks++; return -2; }")
    edit("      if (key->v == value) return e - 1;", "      if (key->v == value) { mp_nobox_hits++; return e - 1; }")
    source = source[:start] + body + source[end:]
Path(sys.argv[2]).write_text(source)
