/* An exact graph and clock oracle for GC work counters. Replace only this
   probe's conservative stack range and clock; collect/scan/sweep are runtime.c's
   real implementation. No wall-time assertion or collector-policy override. */
static void *probe_frame;
#define __builtin_frame_address(n) probe_frame
#define clock_gettime probe_clock_gettime
#include "../runtime.c"
#undef __builtin_frame_address
#undef clock_gettime

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static uint64_t ticks;
static _Noreturn void bad(const char *why) { fprintf(stderr, "gcprofileprobe: %s\n", why); exit(1); }
int probe_clock_gettime(clockid_t clock, struct timespec *t) {
  if (clock != CLOCK_MONOTONIC) bad("unexpected clock");
  uint64_t ns = ++ticks * 1000000;     /* one millisecond per call, not a measurement */
  t->tv_sec = (time_t)(ns / 1000000000); t->tv_nsec = (long)(ns % 1000000000);
  return 0;
}

static void counts(uint64_t marked, uint64_t scanned, uint64_t heap) {
#ifdef PYSTACHY_GC_PROFILE
  uint64_t n = gc_stats ? (uint64_t)gc_n : 0;
  if (gc_marked_objects != (gc_stats ? marked : 0)) bad("marked objects must include atomic objects exactly once");
  if (gc_scanned_objects != (gc_stats ? scanned : 0)) bad("scanned objects must exclude atomic objects");
  if (gc_heap_words != (gc_stats ? heap : 0)) bad("heap words must include each scanned slot, without root words");
  /* Four explicit stack words, one program global, ch1[256], args and warnopts. */
  if (gc_root_words != n * 263) bad("root range accounting");
  if (gc_roots_ns != n * 1000000 || gc_trace_ns != n * 1000000 || gc_sweep_ns != n * 1000000)
    bad("collection phase boundaries");
  if ((uint64_t)gc_ns != gc_roots_ns + gc_trace_ns + gc_sweep_ns) bad("collection phases must partition total time");
#else
  (void)marked; (void)scanned; (void)heap;
  if (gc_ns != (gc_stats ? gc_n * 1000000 : 0)) bad("ordinary stats changed");
#endif
}

int main(void) {
  W stack[4] = {0};
  W *atomic_large = NULL;
  I *roots[] = {(I *)&atomic_large};
  probe_frame = stack;
  gc_init((char *)stack, roots, 1);
  gc_bottom = (char *)(stack + 4);   /* a deterministic stack, with no incidental C roots */
  if (gc_stress || gc_off) bad("run with ordinary collection policy and no inherited stress setting");
  W *a = pys_alloc(23), *b = pys_alloc(23), *c = pys_alloc(23), *dead = pys_alloc(23);
  W *atomic = pys_alloc_atomic(23), *large = pys_alloc(16384);
  atomic_large = pys_alloc_atomic(16384);
  a[0] = (W)b; a[1] = (W)atomic; b[0] = (W)c; c[0] = (W)a;
  large[2047] = (W)b;               /* an edge after several 4 KiB trace slices */
  atomic[0] = (W)dead; atomic_large[0] = (W)dead;
  dead[0] = (W)dead; dead[1] = 999; /* reachable only through atomic pointer-looking bits */
  stack[0] = (W)a; stack[1] = (W)(a + 1); stack[2] = (W)large; stack[3] = (W)(atomic + 1);
  collect();
  if (gc_n != 1) bad("unexpected collection count");
  counts(6, 4, 3 * 3 + 2048);
  if (a[0] != (W)b || a[1] != (W)atomic || b[0] != (W)c || c[0] != (W)a ||
      large[2047] != (W)b || atomic[0] != (W)dead || atomic_large[0] != (W)dead)
    bad("collection changed a live graph");
  /* dead shares a scanned size class with a/b/c, so its dead slot stays mapped. */
  if (dead[1]) bad("atomic payload retained an unreachable object");
  W *old_atomic_large = atomic_large;
  atomic_large = NULL; a[1] = 0; stack[1] = stack[2] = stack[3] = 0;
  collect();
  if (gc_n != 2) bad("unexpected second collection count");
  counts(9, 7, 6 * 3 + 2048);
  if (a[0] != (W)b || b[0] != (W)c || c[0] != (W)a) bad("cycle lost on a later collection");
  if (gc_find(atomic) || gc_find(large) || gc_find(old_atomic_large)) bad("unrooted storage survived");
  if (msp) bad("mark stack was not drained");
  puts("gcprofileprobe: reachability and counters agree");
  if (gc_stats) gc_report();
  return 0;
}
