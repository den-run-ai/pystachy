/* Collector-level weak-reference contracts. Stack scrubbing removes stale conservative
   roots from returned helper frames; no test assumes CPython's immediate refcount timing.
   This includes the real collector and links runtime.py, as listprobe/fileprobe do. */
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static List *refs;
static void *strong;
static I *roots[] = {(I *)&refs, (I *)&strong};
static _Noreturn void bad(const char *what) { fprintf(stderr, "weakrefprobe: %s\n", what); exit(1); }

__attribute__((noinline)) static void scrub_collect(void) {
  volatile I pad[4096];
  for (I i = 0; i < 4096; i++) pad[i] = 0;
  collect();
  if (pad[0]) bad("stack scrub");
}

__attribute__((noinline)) static void make_pair(I size) {
  I *target = pys_alloc(size);
  target[0] = (I)target;              /* a cycle is not sufficient to keep a referent alive */
  target[1] = 321;
  strong = target;
  pys_track(target, size, 0);        /* the same owner exercises the independent ffi.track sweep */
  for (I i = 0; i < 2; i++) {
    WeakRef *r = pys_weakref_new(target);
    if (!(gc_seg(r)->k & 1)) bad("weak handle must be atomic");
    pys_list_append(refs, (I)r);     /* can collect between handle allocation and publication */
  }
}

__attribute__((noinline)) static void check_alive(void) {
  if (pys_collected()) bad("live tracked owner released");
  for (I i = refs->len - 2; i < refs->len; i++) {
    I *target = pys_weakref_get((WeakRef *)refs->a[i]);
    if (target != strong || !target || target[1] != 321) bad("live target lost");
  }
}

__attribute__((noinline)) static void check_dead(void) {
  for (I i = 0; i < refs->len; i++)
    if (pys_weakref_get((WeakRef *)refs->a[i])) bad("dead target retained or revived");
}

__attribute__((noinline)) static void churn(void) {
  for (I i = 0; i < 1000; i++) {
    I *target = pys_alloc(16);
    target[0] = i;
    WeakRef *r = pys_weakref_new(target);
    if (pys_weakref_get(r) != target) bad("new reference has wrong target");
  }
}

__attribute__((noinline)) static I registry_size(void) {
  I n = 0;
  for (WeakRef *r = weakrefs; r; r = r->next) n++;
  return n;
}

__attribute__((noinline)) static void exercise(void) {
  refs = pys_list_new(4);
  make_pair(16);
  scrub_collect(); check_alive();
  strong = NULL;
  scrub_collect(); check_dead();
  if (pys_collected() != 16 || pys_collected()) bad("small tracked owner not released exactly once");
  make_pair(16384);                 /* large objects use a separate allocation and sweep path */
  scrub_collect(); check_alive();
  strong = NULL;
  scrub_collect(); check_dead();
  if (pys_collected() != 16384 || pys_collected()) bad("large tracked owner not released exactly once");
  churn();                         /* dead handles must neither leak nor retain their target */
  scrub_collect(); scrub_collect(); check_dead();
  if (pys_collected()) bad("tracked owner released twice after churn");
  if (registry_size() != refs->len) bad("unreachable weak handles retained by registry");
  pys_list_clear(refs);             /* also clear the carrier if its old address remains on the stack */
  refs = NULL;
}

int main(void) {
  gc_init(__builtin_frame_address(0), roots, 2);
  exercise();
  scrub_collect(); scrub_collect();
  if (registry_size() != 0) bad("registry not empty after dropping all references");
  puts("weakrefprobe: live targets, dead cycles, large objects, reuse, registry pruning and tracked owners passed");
  return 0;
}
