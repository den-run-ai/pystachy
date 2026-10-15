/* Empty reachable lists must not retain their historical capacity. Range-list backing
   is pointer-free, while headers and general list backing are scanned. These are deterministic
   allocation-kind, capacity and live-byte checks, not RSS/timing thresholds. Like dictprobe,
   this includes the real runtime and links runtime.py's IR. usage: make listprobe */
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static List *buffers;
static I *roots[] = {(I *)&buffers};
static _Noreturn void bad(const char *what) { fprintf(stderr, "listprobe: %s\n", what); exit(1); }
static int atomic(void *p) {
  uintptr_t w = (uintptr_t)p; Seg **m = pmap[w >> 30], *s = m ? m[w >> 12 & 0x3ffff] : 0;
  if (!s) bad("list storage outside the heap");
  return s->k & 1;
}
static void kinds(List *l, int pointer_free) {
  if (atomic(l) || atomic(l->a) != pointer_free) bad("list header/backing allocation kind");
}
static void check_empty(List *l) {
  if (l->len || l->cap > 4 || !l->a) bad("empty list retains backing capacity");
}
__attribute__((noinline)) static void clear_many(void) {
  buffers = pys_list_new(64);
  for (I i = 0; i < 64; i++) {
    List *l = pys_list_new(65536);
    l->len = 65536;
    I before = gc_tick;
    pys_list_clear(l);
    check_empty(l);
    if (gc_tick != before) bad("clear allocates");
    pys_list_append(buffers, (I)l);
  }
}
__attribute__((noinline)) static void scrub_collect(void) {
  volatile I pad[4096];                /* erase conservative roots in the dead allocation frames */
  for (I i = 0; i < 4096; i++) pad[i] = 0;
  collect();
  if (pad[0]) bad("scrub");
}
static void operations(void) {
  for (I how = 0; how < 4; how++) {
    List *l = pys_list_new(65536);
    pys_list_append(l, 7);
    if (how == 0) { if (pys_list_pop(l, -1) != 7) bad("pop value"); }
    else if (how == 1) pys_list_del(l, 0);
    else pys_list_imul(l, how == 2 ? 0 : -1);
    check_empty(l);
    pys_list_extend(l, l);
    List *r = pys_list_copy(l);
    pys_list_extend(l, r);
    if (l->len || r->len) bad("empty copy/extend");
    pys_list_append(l, 9);
    if (l->len != 1 || l->cap != 4 || l->a[0] != 9) bad("append after empty");
    pys_list_extend(l, l);
    if (l->len != 2 || l->a[0] != 9 || l->a[1] != 9) bad("self-extend after empty");
  }
  List l = {0, 0, sorting};
  pys_list_clear(&l);
  if (l.a != sorting) bad("clear modifies untouched sort sentinel");
  pys_list_append(&l, 1);
  pys_list_clear(&l);
  if (l.a == sorting) bad("clear hides mutation during sort");
}
static void ranges(void) {
  buffers = pys_list_new(8);
  kinds(buffers, 0);
  I lengths[] = {0, 3, 8, 8192};
  for (I k = 0; k < 4; k++) {
    I n = lengths[k];
    List *l = pys_range_list(2, 2 + 3 * n, 3);
    pys_list_append(buffers, (I)l);
    kinds(l, 1);                     /* includes empty, small-object and large-object backing */
    scrub_collect();
    if (l->len != n || l->cap != (n > 4 ? n : 4)) bad("range-list length/capacity");
    for (I i = 0; i < n; i++) if (l->a[i] != 2 + 3 * i) bad("range-list values");
    List *copy = pys_list_copy(l), *slice = pys_list_slice(l, 1, n - 1);
    kinds(copy, 0); kinds(slice, 0);   /* copies do not yet preserve pointer-free backing */
    if (copy->len != n || slice->len != (n > 2 ? n - 2 : 0)) bad("range-list copy/slice length");
    for (I i = 0; i < n; i++) if (copy->a[i] != 2 + 3 * i) bad("range-list copy values");
    for (I i = 0; i < slice->len; i++) if (slice->a[i] != 5 + 3 * i) bad("range-list slice values");
    if (n) { pys_list_set(l, 0, -7); if (pys_list_get(l, 0) != -7) bad("range-list set"); }
    I cap = l->cap;
    while (l->len < cap) pys_list_append(l, 9);
    kinds(l, 1);                     /* writes within the original buffer keep its kind */
    pys_list_append(l, 11);
    kinds(l, 0);                     /* generic growth remains conservatively scanned */
    if (l->len != cap + 1 || l->a[cap] != 11 || (n && l->a[0] != -7)) bad("range-list growth");
  }
  scrub_collect(); scrub_collect();
  for (I i = 0; i < buffers->len; i++) {
    List *l = (List *)buffers->a[i];
    if (l->a[l->len - 1] != 11) bad("range-list growth lost through collection");
    pys_list_clear(l); check_empty(l);
    pys_list_append(l, 13);
    if (l->len != 1 || l->a[0] != 13) bad("range-list reuse after clear");
  }
  List *descending = pys_range_list(7, -3, -3);
  kinds(descending, 1);
  if (descending->len != 4 || descending->a[0] != 7 || descending->a[3] != -2) bad("descending range-list");
}
int main(void) {
  gc_init(__builtin_frame_address(0), roots, 1);
  clear_many();
  scrub_collect();
  scrub_collect();
  if (gc_live >= 1048576) bad("cleared list storage survives collection");
  for (I i = 0; i < buffers->len; i++) check_empty((List *)buffers->a[i]);
  operations();
  ranges();
  puts("listprobe: empty-list reuse and range-list storage/mutation passed");
  return 0;
}
