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
enum { RAW_STORE_CLASS = 73 };
I pys_obj_cmp(I c, I op, I a, I b) {
  if (c == -1 - RAW_STORE_CLASS && op == 1) {
    Dyn *item = (Dyn *)b;
    if (DKIND(item) == DK_INT && item->v == 1) { pys_list_set((List *)a, 1, 9); return 0; }
    return DKIND(item) == DK_INT && item->v == 9;
  }
  return a < b ? -1 : a > b;
}
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
  List l = {0, 0, sorting, 0};
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
/* Dynamic graphs keep scalar identity separately from raw numeric storage. Copies and
   mutators move that provenance with the values; matching payload bits never merge boxes. */
static void identity_slots(List *l) {
  if (!l->ids) bad("numeric identity companion missing");
  for (I i = 0; i < l->len; i++) {
    Dyn *d = (Dyn *)l->ids[i + 1];
    if (!d || d->v != l->a[i]) bad("numeric identity companion differs from payload");
  }
}
static void identities(void) {
  Dyn *a = pys_dyn_float(NAN), *b = pys_dyn_float(NAN), *z = pys_dyn_float(-0.0);
  List *l = pys_list_new_atomic(0);
  buffers = pys_list_new(0); pys_list_append(buffers, (I)l);
  pys_list_append_identity(l, a->v, a, 2);
  pys_list_append_identity(l, b->v, b, 2);
  pys_list_append_identity(l, a->v, a, 2);
  pys_list_append_identity(l, z->v, z, 2);
  identity_slots(l); kinds(l, 1);
  if (atomic(l->ids)) bad("numeric identity companion is not scanned");
  if (pys_list_get_identity(l, -4, 2) != a) bad("negative identity index");
  if (pys_list_count_identity(l, a->v, a, cstr("f"), cstr("f"), 2) != 2) bad("NaN identity count");
  if (pys_list_index_identity(l, b->v, b, cstr("f"), cstr("f"), 2, 0, 100) != 1) bad("distinct NaN identity index");
  I ticks = gc_tick;
  pys_list_set(l, 1, a->v);
  if (gc_tick != ticks || l->ids[2]) bad("raw list store allocates instead of invalidating identity");
  if (!eqv((I)l, (I)l, "Lf")) bad("pending numeric identity loses list self equality");
  List *q = pys_list_copy(l);
  if (!l->ids[2] || l->ids[2] != q->ids[2] || l->ids[2] == (I)a) bad("copy did not materialize a fresh raw-store identity");
  pys_list_set_identity(l, 1, b->v, b, 2);
  pys_list_set_identity(q, 1, b->v, b, 2);
  if (!eqv((I)l, (I)q, "Lf") || !eqpair((I)l, (I)q, "Lf", "Lf") || !opv((I)l, (I)q, "Lf", 1)) bad("NaN identity sequence comparison");
  pys_list_reverse(q); identity_slots(q);
  if (q->ids[1] != (I)z || q->ids[4] != (I)a) bad("reverse loses identity");
  List *r = pys_list_slice_step(l, NONE, NONE, -1);
  identity_slots(r); if (r->ids[1] != (I)z) bad("stepped slice loses identity");
  pys_list_extend(l, l); pys_list_imul(l, 3); identity_slots(l);
  if (l->len != 24 || l->ids[1] != l->ids[5] || l->ids[24] != (I)z) bad("self extend/repeat identity");
  List *m = pys_list_mul(q, 3); identity_slots(m);
  if (m->len != 12 || m->ids[12] != (I)a) bad("repetition loses identity");
  pys_list_set_slice(m, 1, 5, 1, q); identity_slots(m);
  pys_list_set_slice(m, 0, 4, 1, m); identity_slots(m);
  if (m->len != 20) bad("identity self slice assignment length");
  pys_list_del_slice(m, 0, 20, 3); identity_slots(m);
  pys_list_del_slice(m, NONE, NONE, -2); identity_slots(m);
  pys_list_insert_identity(m, -100, a->v, a, 2); identity_slots(m);
  if (pys_list_pop_identity(m, 0, 2) != a) bad("pop loses identity");
  identity_slots(m);
  pys_list_remove_identity(l, b->v, b, cstr("f"), cstr("f"), 2); identity_slots(l);
  if (l->len != 23) bad("remove of aliased NaN");
  pys_list_clear(l); check_empty(l);
  if (l->ids != empty_identity_float) bad("clear retains identity backing");
  pys_list_append_identity(l, z->v, z, 2); identity_slots(l);
  pys_list_forget_identity(l); identity_slots(l);
  if (l->ids[1] == (I)z) bad("native writeback retained old float identity");
  for (I i = 0; i < 100; i++) {
    Dyn *x = pys_dyn_float((double)((99 - i) % 17));
    pys_list_append_identity(l, x->v, x, 2);
  }
  List *before = pys_list_copy(l);
  pys_list_sort(l, cstr("f")); identity_slots(l);
  for (I i = 0; i < l->len; i++) {
    I found = 0;
    for (I j = 0; j < before->len; j++) found += l->ids[i + 1] == before->ids[j + 1];
    if (!found || (i && dbl(l->a[i - 1]) > dbl(l->a[i]))) bad("sort loses value/identity");
  }
  if (pys_list_minmax_identity(l, cstr("f"), 0, 2) != (Dyn *)l->ids[1]) bad("min loses identity");
  List *taken = pys_list_take(l), *keys = pys_list_new_atomic(taken->len);
  for (I i = 0; i < taken->len; i++) pys_list_append(keys, taken->len - i);
  List *pairs = pys_list_keyed(taken, keys, 1);
  pys_list_sort(pairs, cstr("Ki")); pys_list_unkey(taken, pairs); pys_list_give(taken);
  identity_slots(l);
  for (I i = 1; i < l->len; i++) if (dbl(l->a[i - 1]) < dbl(l->a[i])) bad("keyed sort loses identity order");
  List *native = pys_list_new_atomic(0);
  pys_list_append(native, 1000); pys_list_identity(native, 1);
  Dyn *old = pys_list_get_identity(native, 0, 1);
  pys_list_append(native, 1000); identity_slots(native);
  if (pys_list_get_identity(native, 1, 1) == old) bad("raw numeric write reused an equal object's identity");
}
/* Promoting storage and numeric identity share a scanned companion. The first
   observation upgrades Mpz entries to boxes; every list move must preserve them. */
static void wide_identities(void) {
  Mpz *bigint = pys_mpz_from_str(cstr("1180591620717411303424"), 10);
  Mpz *negative = pys_mpz_unary(bigint, 0);
  Dyn *a = pys_dyn_big(0, bigint), *b = pys_dyn_big(0, bigint);
  List *l = pys_list_new_atomic(0);
  buffers = pys_list_new(0); pys_list_append(buffers, (I)l);
  pys_list_append(l, INT64_MIN);
  pys_list_append_big(l, bigint);
  pys_list_append(l, 1000);
  if (!big_list(l) || lbig(l, 0) || lbig(l, 1) != bigint) bad("initial promoting list storage");
  pys_list_identity(l, 1);
  if (big_list(l) || lbig(l, 0) || lbig(l, 1) != bigint || atomic(l->a) != 1 || atomic(l->ids)) bad("promoting identity upgrade");
  Dyn *first = pys_list_get_identity(l, 1, 1);
  if (pys_dyn_big_ptr(first) != bigint) bad("wide list read identity");
  pys_list_set_identity(l, 1, INT64_MIN, a, 1);
  pys_list_append_identity(l, INT64_MIN, b, 1);
  pys_list_append_identity(l, INT64_MIN, a, 1);
  if (a == b || pys_list_get_identity(l, 1, 1) != a || pys_list_get_identity(l, 3, 1) != b) bad("equal wide identities collapsed");
  List *copy = pys_list_copy(l); pys_list_append(buffers, (I)copy);
  List *slice = pys_list_slice_step(l, NONE, NONE, -1); pys_list_append(buffers, (I)slice);
  if (copy->ids[2] != (I)a || slice->ids[1] != (I)a || slice->ids[2] != (I)b) bad("wide copy/slice identity");
  pys_list_reverse(copy);
  if (copy->ids[1] != (I)a || copy->ids[2] != (I)b) bad("wide reverse identity");
  List *plain = pys_list_new_atomic(0);
  pys_list_append_big(plain, negative);
  pys_list_extend(plain, l);
  if (big_list(plain) || lbig(plain, 0) != negative || plain->ids[3] != (I)a) bad("raw/identity extend upgrade");
  pys_list_set_slice(plain, 0, 2, 1, copy);
  if (plain->ids[1] != (I)a || plain->ids[2] != (I)b) bad("wide slice assignment identity");
  pys_list_extend(l, l);
  pys_list_imul(l, 2);
  if (l->len != 20 || l->ids[2] != (I)a || l->ids[4] != (I)b || l->ids[17] != (I)a) bad("wide repeated identity");
  pys_list_sort(l, cstr("i"));
  for (I i = 1; i < l->len; i++) {
    Big x = litem(l, i - 1), y = litem(l, i);
    if (pys_big_cmp(x.lo, x.hi, y.lo, y.hi) > 0) bad("wide identity sort order");
  }
  if (l->ids[9] != (I)a || l->ids[10] != (I)b || l->ids[11] != (I)a) bad("wide identity stable sort");
  if (pys_list_minmax_identity(l, cstr("i"), 1, 1) != a) bad("wide max preserves first equal identity");
  if (pys_list_find_identity(l, INT64_MIN, pys_dyn_int(INT64_MIN), cstr("i"), cstr("i"), 1) != 0) bad("wide items mistaken for INT64_MIN");
  Dyn *floatbig = pys_dyn_float(1180591620717411303424.0);
  if (pys_list_count_identity(l, floatbig->v, floatbig, cstr("i"), cstr("f"), 1) != 12) bad("wide identity float search");
  Big sum = pys_big_sum(copy, 0, NULL);
  if (strcmp(pys_big_str(sum.lo, sum.hi)->s, "3532551490115379135464")) bad("wide identity sum");
  Dict *keys = pys_dict_fromkeys(0, copy, 7);
  if (keys->len != 3 || pys_dict_big_find(keys, 0, bigint) < 0) bad("wide identity dict.fromkeys");
  if (pys_list_pop_identity(copy, 0, 1) != a) bad("wide pop identity");
  pys_list_insert_big(copy, 0, negative);
  if (lbig(copy, 0) != negative || !pys_dyn_big_ptr(pys_list_get_identity(copy, 0, 1))) bad("wide raw insertion into identity list");
  pys_list_set_big(copy, 0, bigint);
  if (lbig(copy, 0) != bigint) bad("wide raw replacement into identity list");
  pys_list_append_big(copy, negative);
  if (lbig(copy, copy->len - 1) != negative) bad("wide raw append into identity list");
  scrub_collect();
  if (pys_mpz_cmp(lbig(copy, 0), bigint) || l->ids[9] != (I)a) bad("wide companion survives collection");
  pys_list_clear(copy); check_empty(copy);
  pys_list_append_big(copy, bigint);
  if (lbig(copy, 0) != bigint || big_list(copy)) bad("cleared identity list keeps wide representation");
  List *empty_big = pys_list_new_atomic(0);
  pys_list_append_big(empty_big, bigint); pys_list_clear(empty_big);
  pys_list_identity(empty_big, 1);
  if (empty_identity_big[0] != BIGIDS || empty_big->ids != empty_identity_int) bad("empty upgrade mutated shared sentinel");
}
static void query_mutation(void) {
  /* A comparison can call code using the raw numeric ABI. The next item needs
     its newly stored value's box, not the old box or a pending null companion. */
  List *l = pys_list_new_atomic(0);
  pys_list_append(l, 1); pys_list_append(l, 2);
  DynType type = {DK_OBJ, cstr("O73"), cstr("RawStore"), RAW_STORE_CLASS, 0, DF_X, 0, 0, 0};
  Dyn *query = pys_dyn_ref(&type, l);
  if (pys_list_find_identity(l, (I)query, query, cstr("i"), cstr("A"), 1) != 1)
    bad("dynamic query does not observe callback raw store");
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
  identities();
  wide_identities();
  query_mutation();
  budgets();
  puts("listprobe: empty-list reuse, range-list storage/mutation, pointer-free list kinds, numeric identity, promoting storage and large-object collections passed");
  return 0;
}
