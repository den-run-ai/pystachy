/* Probe both the post-return global roots and forced collections inside guest activations. */
#define pys_finish finish_without_probe
#define pys_gc_collect collect_without_probe
#include "../runtime.c"
#undef pys_finish
#undef pys_gc_collect

static int local_collections;

/* Zero the dead stack below the caller. Frames that have returned, the runtime's root frames
   among them (wasm/spill_roots.py), leave words a conservative scan would take for references,
   and these probes ask what the roots alone retain. Each probe entry calls it from a frameless
   wrapper, so it also clears what lay where the probe's own frames now lie. */
__attribute__((noinline)) static void clear_dead_stack(void) {
  volatile char dead[65536];
  for (size_t i = 0; i < sizeof dead; i++) dead[i] = 0;
}

static uintptr_t caller_stack;

/* The arrays' sizes identify them independently of unrelated runtime objects.
   Only require live roots: a conservative C stack scan may retain stale ones. */
static void check_local_arrays(int required) {
  collect();
  int live = 0;
  for (Seg *s = bigs; s; s = s->next)
    for (int i = 0; i < 4; i++)
      if (s->size == (10000 + i) * (I)sizeof(I) + 1) live |= 1 << i;
  if ((live & required) != required) {
    fprintf(stderr, "missing guest roots: required %d, found %d\n", required, live);
    exit(1);
  }
}

__attribute__((noinline)) static void probe_collect(void) {
  if (gc_off != wasi_guest_unrooted) exit(1);   /* (automatic collection runs exactly in a rooted guest) */
  if (!gc_nroots) {   /* Textual IR probe: the only reference is packed in i64. */
    if (local_collections++) exit(1);
    check_local_arrays(8);
    return;
  }
  const int required[] = {1, 3, 1, 5, 1};
  uintptr_t sp = (uintptr_t)__builtin_frame_address(0);
  if (local_collections >= 5) exit(1);
  if (!local_collections) caller_stack = sp;
  /* Check restoration independently of conservative reachability. All five
     collections enter through the same gc.collect guest function and C shim. */
  if (local_collections % 2 ? sp >= caller_stack : sp != caller_stack) {
    fputs("guest failed to reserve or restore its root frame\n", stderr);
    exit(1);
  }
  check_local_arrays(required[local_collections++]);
}

__attribute__((noinline)) static void probe_finish(void) {
  if (local_collections) {
    if (local_collections != (gc_nroots ? 5 : 1)) exit(1);
    finish_without_probe();
    return;
  }
  if (!gc_off || gc_nroots != 2) {
    fputs("expected disabled automatic collection and two program roots\n", stderr);
    exit(1);
  }
  collect();
  I live_headers = 0;
  for (Seg *s = chunks; s; s = s->next)
    if (s->k == 2 * cls(sizeof(List) - 1)) live_headers += s->nlive;
  if (live_headers != 2) {
    fprintf(stderr, "expected two live list headers, found %lld\n", (long long)live_headers);
    exit(1);
  }
  I values = 0;
  for (I i = 0; i < gc_nroots; i++) {
    List *list = *(List **)gc_roots[i];
    if (list && list->len == 1) {
      if (list->a[0] == 23) values |= 1;
      if (list->a[0] == 29) values |= 2;
    }
  }
  if (values != 3) {
    fputs("retained list contents differ\n", stderr);
    exit(1);
  }
  finish_without_probe();
}

void pys_gc_collect(void) { clear_dead_stack(); probe_collect(); }
void pys_finish(void) { clear_dead_stack(); probe_finish(); }
