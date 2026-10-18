/* Empty reachable lists must not retain their historical capacity. The item arrays of range
   lists and of pys_list_new_atomic's lists (the compiler's list[int], list[float] and list[bool])
   are pointer-free, and so are the arrays that growth, copies, slices, + and * make of them, and
   a cleared one's sentinel; headers and other lists' arrays are scanned, and stay so through the
   same operations. Ints in a pointer-free array that are the addresses of objects keep none of
   them alive. Dropped pointer-free large item arrays that are most of what is allocated start
   collections of their own, every max(4 MiB, live bytes) of them; small objects, large arrays
   among more small objects and arrays of pointers keep the 32 MiB window. These are
   deterministic allocation-kind, capacity, live-byte and collection-count checks, not RSS/timing
   thresholds. Like dictprobe, this includes the real runtime and links runtime.py's IR.
   usage: make listprobe */
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
  for (I how = 0; how < 3; how++) {    /* slice assignment and deletion that empty a list */
    List *l = pys_list_new(65536), *none = pys_list_new(0);
    for (I i = 0; i < 9; i++) pys_list_append(l, i);
    if (how == 0) pys_list_set_slice(l, NONE, NONE, 1, none);
    else pys_list_del_slice(l, NONE, NONE, how == 1 ? 1 : -1);
    check_empty(l);
  }
  List l = {0, 0, sorting};
  pys_list_del_slice(&l, NONE, NONE, 1);
  pys_list_del_slice(&l, NONE, NONE, 2);
  pys_list_set_slice(&l, NONE, NONE, 1, &l);
  if (l.a != sorting || l.len) bad("an empty slice change modifies the sort sentinel");
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
    kinds(copy, 1); kinds(slice, 1);   /* copies keep the pointer-free kind */
    if (copy->len != n || slice->len != (n > 2 ? n - 2 : 0)) bad("range-list copy/slice length");
    for (I i = 0; i < n; i++) if (copy->a[i] != 2 + 3 * i) bad("range-list copy values");
    for (I i = 0; i < slice->len; i++) if (slice->a[i] != 5 + 3 * i) bad("range-list slice values");
    if (n) { pys_list_set(l, 0, -7); if (pys_list_get(l, 0) != -7) bad("range-list set"); }
    I cap = l->cap;
    while (l->len < cap) pys_list_append(l, 9);
    kinds(l, 1);                     /* writes within the original buffer keep its kind */
    pys_list_append(l, 11);
    kinds(l, 1);                     /* and so does growth */
    if (l->len != cap + 1 || l->a[cap] != 11 || (n && l->a[0] != -7)) bad("range-list growth");
  }
  scrub_collect(); scrub_collect();
  for (I i = 0; i < buffers->len; i++) {
    List *l = (List *)buffers->a[i];
    if (l->a[l->len - 1] != 11) bad("range-list growth lost through collection");
    pys_list_clear(l); check_empty(l);
    if (l->a != empty_atomic) bad("a cleared range list forgets its kind");
    pys_list_append(l, 13);
    kinds(l, 1);
    if (l->len != 1 || l->a[0] != 13) bad("range-list reuse after clear");
  }
  List *descending = pys_range_list(7, -3, -3);
  kinds(descending, 1);
  if (descending->len != 4 || descending->a[0] != 7 || descending->a[3] != -2) bad("descending range-list");
  List *r = pys_range_list(0, 6, 1), *two = pys_list_new(2), *seven = pys_range_list(0, 7, 1);
  pys_list_append(two, 7); pys_list_append(two, 8);
  pys_list_set_slice(r, 1, NONE, 3, two);         /* r[1::3] = [7, 8] */
  pys_list_del_slice(r, NONE, NONE, -2);          /* del r[::-2] */
  pys_list_set_slice(r, 1, 2, 1, two);            /* r[1:2] = [7, 8], within the capacity */
  kinds(r, 1);                                    /* changes within the backing keep its kind */
  if (r->len != 4 || r->a[0] != 0 || r->a[1] != 7 || r->a[2] != 8 || r->a[3] != 8) bad("range-list slice changes");
  pys_list_set_slice(r, NONE, NONE, 1, seven);
  kinds(r, 1);                                    /* growth past it keeps the kind */
  if (r->len != 7 || r->a[6] != 6) bad("range-list slice growth");
}
static Str *big(I i) {                 /* a str of 1 MiB; its first byte tells i */
  Str *s = pys_str_mul(cstr("x"), 1 << 20); s->s[0] = (char)('a' + i); return s;
}
static void same(List *l, I n, I first, I step, const char *what) {
  if (l->len != n) bad(what);
  for (I i = 0; i < n; i++) if (l->a[i] != first + i * step) bad(what);
}
__attribute__((noinline)) static void addresses(void) {   /* the 16 strs' addresses, in a pointer-free list only */
  List *a = pys_list_new_atomic(0), *h = pys_list_new(16);
  buffers = pys_list_new(2); pys_list_append(buffers, (I)a); pys_list_append(buffers, (I)h);
  for (I i = 0; i < 16; i++) { I x = (I)big(i); pys_list_append(h, x); pys_list_append(a, x); }
  buffers->a[1] = 0; buffers->len = 1;   /* (h kept the strs apart; now nothing scanned holds them) */
}
__attribute__((noinline)) static void held(void) {        /* the same in a scanned list keeps them */
  List *h = pys_list_new(0);
  buffers = pys_list_new(1); pys_list_append(buffers, (I)h);
  for (I i = 0; i < 16; i++) pys_list_append(h, (I)big(i));
}
/* the operations that make an item array, on a list of each kind: they keep it */
static void numeric(void) {
  for (int pf = 0; pf < 2; pf++) {
    List *l = pf ? pys_list_new_atomic(0) : pys_list_new(0), *k;
    buffers = pys_list_new(16); pys_list_append(buffers, (I)l);
    kinds(l, pf);
    for (I i = 0; i < 100; i++) pys_list_append(l, i);          /* growth, small arrays to large */
    kinds(l, pf); same(l, 100, 0, 1, "appended items");
    pys_list_insert(l, 0, -1); pys_list_del(l, 0); kinds(l, pf);
    k = pys_list_copy(l); pys_list_append(buffers, (I)k); kinds(k, pf); same(k, 100, 0, 1, "copy");
    k = pys_list_slice(l, 10, 20); pys_list_append(buffers, (I)k); kinds(k, pf); same(k, 10, 10, 1, "slice");
    k = pys_list_slice_step(l, 99, NONE, -3); pys_list_append(buffers, (I)k); kinds(k, pf); same(k, 34, 99, -3, "slice step");
    k = pys_list_mul(l, 3); pys_list_append(buffers, (I)k); kinds(k, pf);
    if (k->len != 300 || k->a[299] != 99 || k->a[100] != 0) bad("list * n");
    k = pys_list_mul(pys_list_slice(l, 0, 0), 5); pys_list_append(buffers, (I)k); kinds(k, pf);
    k = pys_list_add(l, l); pys_list_append(buffers, (I)k); kinds(k, pf);
    k = pys_list_add(l, pys_list_new(0)); pys_list_append(buffers, (I)k); kinds(k, 0);   /* (one scanned array: scanned) */
    k = pys_list_add(pys_range_list(0, 3, 1), pys_list_new_atomic(0)); pys_list_append(buffers, (I)k); kinds(k, 1);
    k = pys_list_copy(l); pys_list_append(buffers, (I)k);
    pys_list_imul(k, 4); kinds(k, pf); if (k->len != 400) bad("list *= n");
    pys_list_extend(k, l); kinds(k, pf);
    pys_list_set_slice(k, 0, 1, 1, pys_list_mul(l, 20)); kinds(k, pf);
    pys_list_sort(l, cstr("i")); kinds(l, pf); same(l, 100, 0, 1, "sort");
    pys_list_clear(k); check_empty(k);
    if (k->a != (pf ? empty_atomic : empty_list)) bad("cleared list's sentinel");
    pys_list_append(k, 5); kinds(k, pf);
    while (k->len) pys_list_pop(k, -1);
    if (k->a != (pf ? empty_atomic : empty_list)) bad("emptied list's sentinel");
    k = pys_list_copy(k); pys_list_append(buffers, (I)k); kinds(k, pf);   /* (the copy of an empty list) */
    scrub_collect();
    same(l, 100, 0, 1, "items through collection");
  }
  Dict *d = pys_dict_new(0, 0), *s = pys_dict_new(1, 0); Set *t = pys_set_new(0), *u = pys_set_new(0);
  buffers = pys_list_new(4); buffers->a[0] = (I)d; buffers->a[1] = (I)s; buffers->a[2] = (I)t; buffers->a[3] = (I)u; buffers->len = 4;
  for (I i = 0; i < 100; i++) { pys_dict_set(d, i, i * 2); pys_dict_set(s, (I)cstr("k"), i); pys_set_add(t, i); }
  pys_set_add(u, 1);
  kinds(pys_dict_keys(d), 1); kinds(pys_dict_values(d), 0); kinds(pys_dict_keys(s), 0);   /* (int keys only) */
  kinds(pys_set_list(t), 1); kinds(pys_set_list(u), 0);   /* (an int set's first 8 slots are scanned) */
  same(pys_dict_keys(d), 100, 0, 1, "dict keys"); same(pys_dict_values(d), 100, 0, 2, "dict values");
  addresses(); scrub_collect(); scrub_collect();
  if (gc_live >= 4 << 20) bad("ints that are the addresses of strs, in a pointer-free list, kept them alive");
  if (((List *)buffers->a[0])->len != 16) bad("the addresses' list lost");
  held(); scrub_collect(); scrub_collect();
  if (gc_live < 16 << 20) bad("a scanned list's strs were freed");
  List *h = (List *)buffers->a[0];
  for (I i = 0; i < 16; i++) { Str *x = (Str *)h->a[i]; if (x->len != 1 << 20 || x->s[0] != 'a' + i) bad("a kept str changed"); }
  buffers = 0;
}
__attribute__((noinline)) static I churn(I n, I *most) {   /* n dropped lists of 8192 floats: their item
                                                               arrays are large objects of 64 KiB */
  I before = gc_n;
  for (I i = 0; i < n; i++) {
    pys_list_new_atomic(8192);
    if (gc_heap > *most) *most = gc_heap;
  }
  return gc_n - before;
}
/* The candidate's bytes count toward the small large-object budget only when pointer-free.
   A single scanned block above 4 MiB exposed this; the 64 KiB churn below cannot. Run first
   so the empty-heap case has no allocation history, then check a mixed history and both
   positive controls. GC stress deliberately collects at each allocation instead. */
static void budget_candidates(void) {
  I before = gc_n;
  pys_alloc(5 << 20);
  if (!gc_stress && gc_n != before) bad("a scanned candidate uses the pointer-free budget on an empty heap");
  scrub_collect();
  before = gc_n;
  pys_alloc_atomic(3 << 20);
  pys_alloc(2 << 20);
  if (!gc_stress && gc_n != before) bad("a scanned candidate completes the pointer-free budget");
  scrub_collect();
  before = gc_n;
  pys_alloc_atomic(5 << 20);
  if (!gc_stress && gc_n - before != 1) bad("a pointer-free candidate uses its 4 MiB budget");
  scrub_collect();
  before = gc_n;
  pys_alloc(32 << 20);
  if (!gc_stress && gc_n - before != 1) bad("a scanned candidate still uses the 32 MiB budget");
  scrub_collect();
}
/* pointer-free large objects start collections of their own where they are most of what is
   allocated: dropping 32 MiB of large float arrays while little is live runs one every 4 MiB
   of them (BIG_MIN), so the heap grows by about 4 MiB rather than 32; with 8 MiB of them
   live, one every 8 MiB. Small objects, large arrays among more small objects and arrays of
   pointers keep the 32 MiB window. Counts only without GC stress, which collects at every
   allocation */
static void budgets(void) {
  buffers = 0; scrub_collect();
  I base = gc_heap, most = base, runs = churn(512, &most);
  if (!gc_stress && runs != 8) bad("dropped large arrays run a collection every 4 MiB of them");
  if (!gc_stress && most - base > (6 << 20)) bad("dropped large arrays grow the heap past 6 MiB");
  buffers = pys_list_new(128);
  for (I i = 0; i < 128; i++) pys_list_append(buffers, (I)pys_list_new_atomic(8192));
  scrub_collect();
  runs = churn(512, &most);
  if (!gc_stress && runs != 3) bad("the large-object budget follows the live bytes");
  buffers = 0; scrub_collect();
  I before = gc_n;
  for (I i = 0; i < (48 << 20) / 64; i++) pys_alloc_atomic(56);
  if (!gc_stress && gc_n - before != 1) bad("small objects keep the 32 MiB window");
  scrub_collect();
  before = gc_n;                       /* 40 MiB: a 64 KiB array per 192 KiB of small objects */
  for (I i = 0; i < 160; i++) {
    pys_list_new_atomic(8192);
    for (I j = 0; j < 3 * 1024; j++) pys_alloc_atomic(56);
  }
  if (!gc_stress && gc_n - before != 1) bad("large arrays among more small objects keep the 32 MiB window");
  scrub_collect();
  before = gc_n;                       /* 40 MiB of dropped 64 KiB arrays of pointers */
  for (I i = 0; i < 640; i++) pys_list_new(8192);
  if (!gc_stress && gc_n - before != 1) bad("dropped arrays of pointers keep the 32 MiB window");
}
int main(void) {
  gc_init(__builtin_frame_address(0), roots, 1);
  budget_candidates();
  clear_many();
  scrub_collect();
  scrub_collect();
  if (gc_live >= 1048576) bad("cleared list storage survives collection");
  for (I i = 0; i < buffers->len; i++) check_empty((List *)buffers->a[i]);
  operations();
  ranges();
  numeric();
  budgets();
  puts("listprobe: empty-list reuse, range-list storage/mutation, pointer-free list kinds and large-object collections passed");
  return 0;
}
