/* Research adapter included in a generated runtime.c by bdwgc_overlay.py.
   BDWGC owns all managed allocations.  The native allocator and JIT free lists
   stay empty.  This is an AOT, single-mutator experiment, not a full binding. */
#define GC_THREADS
#define GC_NO_THREAD_REDIRECTS
#include <gc/gc.h>
#include <gc/gc_mark.h>

static GC_push_other_roots_proc bdw_previous_roots;
static GC_warn_proc bdw_previous_warn;
static GC_word bdw_peak_heap;
static int bdw_atomic_kind;
static uint64_t bdw_pause_ns, bdw_pause_started, bdw_pauses;
static const char *bdw_mode = "default";

static _Noreturn void bdw_unsupported(const char *feature) {
  fprintf(stderr, "pystachy: experimental BDWGC adapter does not support %s\n", feature);
  fflush(stderr);
  exit(78);
}

/* A nonzero incremental flag alone is insufficient evidence when dirty-page
   tracking reports a capability failure.  Preserve the upstream diagnostic and
   reject this experiment instead of silently ranking an unvalidated fallback.
   Warnings may run while the GC lock is held, so exit without GC finalization. */
static void bdw_warn(char *message, GC_word argument) {
  bdw_previous_warn(message, argument);
  if (strcmp(bdw_mode, "default") && strstr(message, "cannot enable GC incremental mode")) {
    fputs("pystachy: BDWGC incremental capability warning; benchmark sample excluded\n", stderr);
    fflush(stderr);
    _Exit(78);
  }
}

static uint64_t bdw_now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (uint64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

/* A malloc-backed table is not traced just because a static points to it.
   Keep exactly its live range, including active exception cleanup arguments.
   BDWGC also scans native stack/registers and static/global data itself. */
static void bdw_roots(void) {
  if (bdw_previous_roots) bdw_previous_roots();
  for (I i = 0; i < gc_nroots; i++)
    GC_push_all_eager(gc_roots[i], gc_roots[i] + 1);
  if (nprotos) GC_push_all_eager(protos, protos + nprotos);
  if (nunw) GC_push_all_eager(unw, unw + nunw);
}

static void bdw_resize(GC_word size) {
  if (size > bdw_peak_heap) bdw_peak_heap = size;
}

/* START..END can include mutator execution in incremental mode, so it must
   not be reported as GC overhead.  Measure the stopped-world event intervals
   only.  This excludes work outside these intervals and is not GC CPU time. */
static void bdw_event(GC_EventType event) {
  if (event == GC_EVENT_START) memset(text_hints, 0, sizeof text_hints);
  if (gc_stats && event == GC_EVENT_POST_STOP_WORLD) bdw_pause_started = bdw_now();
  if (gc_stats && event == GC_EVENT_PRE_START_WORLD && bdw_pause_started) {
    bdw_pause_ns += bdw_now() - bdw_pause_started;
    bdw_pause_started = 0;
    bdw_pauses++;
  }
}

static void bdw_init(char *sb, I **roots, I nroots) {
  const char *e = getenv("PYSTACHY_GC");
  gc_bottom = sb + 2 * sizeof(void *);
  gc_roots = roots; gc_nroots = nroots;
  gc_off = e && !strcmp(e, "off");
  gc_stats = e && (!strcmp(e, "stats") || !strcmp(e, "profile"));
  if (getenv("PYSTACHY_ARGV0")) bdw_unsupported("JIT execution (signal ownership is unvalidated)");
  if (getenv("PYSTACHY_GC_MIN")) bdw_unsupported("PYSTACHY_GC_MIN (native collection pacing)");
  if (getenv("PYSTACHY_GC_MARK")) bdw_unsupported("PYSTACHY_GC_MARK (native tracing policy)");
  if (!gc_off && (e = getenv("PYSTACHY_GC_STRESS")) && atoll(e) > 0) gc_stress = atoll(e);
  e = getenv("PYSTACHY_BDWGC_MODE");
  if (e && strcmp(e, "default")) {
    if (strcmp(e, "incremental") && strcmp(e, "generational"))
      bdw_unsupported("the requested PYSTACHY_BDWGC_MODE");
    bdw_mode = e;
  }
  bdw_previous_warn = GC_get_warn_proc();
  GC_set_warn_proc(bdw_warn);
  GC_set_all_interior_pointers(1);
  /* Pystachy emits no dirty-object barriers. Some BDWGC builds default to
     manual VDB, which requires them. Disable it before GC_INIT can enable
     incremental collection, and require automatic tracking below. */
  GC_set_manual_vdb_allowed(0);
  GC_set_markers_count(1);             /* one marker, including the mutator */
  GC_set_on_heap_resize(bdw_resize);
  GC_set_on_collection_event(bdw_event);
  bdw_previous_roots = GC_get_push_other_roots();
  GC_set_push_other_roots(bdw_roots);
  GC_INIT();
  void *kind_probe = GC_malloc_atomic(1);
  if (!kind_probe) oom();
  bdw_atomic_kind = GC_get_kind_and_size(kind_probe, NULL);
  GC_free(kind_probe);
  if (strcmp(bdw_mode, "default")) {
    if (gc_off) bdw_unsupported("GC=off combined with incremental/generational mode");
    if (!strcmp(bdw_mode, "generational")) GC_set_time_limit(GC_TIME_UNLIMITED);
    GC_enable_incremental();
    if (!GC_is_incremental_mode()) bdw_unsupported("automatic incremental tracking on this BDWGC build");
  }
  if (gc_off) GC_disable();
}

static void *bdw_alloc(I n, int how) {
  if ((uint64_t)n > (uint64_t)1 << 40) oom();
  if (gc_stress && ++gc_tick >= gc_stress) { gc_tick = 0; GC_gcollect(); }
  size_t size = (size_t)n + 1;         /* retain a pointer one past the payload */
  void *p = (how & 1) ? GC_malloc_atomic(size) : GC_malloc(size);
  if (!p) oom();
  /* GC_malloc_atomic does not promise cleared storage.  pys_new carries an
     LLVM allockind("alloc,zeroed") promise, and ordinary atomic callers read
     unwritten fields.  Only gc_raw (how == 3) can omit zeroing. */
  if ((how & 1) && how != 3) memset(p, 0, size);
  return p;
}

static void bdw_report(void) {
  struct GC_prof_stats_s s;
  GC_get_prof_stats(&s, sizeof s);
  unsigned v = GC_get_version();
  fprintf(stderr, "bdwgc: version=%u.%u.%u mode=%s incremental=%d protection=%d markers=%lu "
          "collections=%lu stopped_world_ms=%.3f pauses=%llu heap_peak_bytes=%llu "
          "heap_bytes=%llu free_bytes=%llu allocated_bytes=%llu\n",
          v >> 16, (v >> 8) & 255, v & 255, bdw_mode,
          GC_is_incremental_mode(), GC_incremental_protection_needs(),
          (unsigned long)s.markers_m1 + 1, (unsigned long)s.gc_no,
          bdw_pause_ns / 1e6, (unsigned long long)bdw_pauses,
          (unsigned long long)bdw_peak_heap,
          (unsigned long long)(s.heapsize_full - s.unmapped_bytes),
          (unsigned long long)(s.free_bytes_full - s.unmapped_bytes),
          (unsigned long long)(s.allocd_bytes_before_gc + s.bytes_allocd_since_gc));
}
