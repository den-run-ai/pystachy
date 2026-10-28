/* Probe counts of the runtime's dict tables, for keys that defeat a weak hash or probe sequence
   (issue #4: keys i << 46 used to pile up in one cluster), with sequential keys as the control.
   It includes runtime.c with DICT_PROBE counting the index slots that lookups, insertions and
   rebuilds visit (normal builds define it as nothing), builds a dict of N keys of each pattern
   (N = 4000, 8000, 16000 and 30000 unless given), and reports the slots visited per operation:
     insert   per insertion, the rebuilds that growth makes included
     hit      per lookup of each key
     miss     per lookup of N keys that are absent
     deleted  per lookup of each key after every other one was deleted (the holes stay)
     longest  the most slots that one of those lookups visited
   A last row sweeps the shifts, keys i << s and -(i << s) for every s up to 56 (8000 keys, fewer
   where 2N of them do not fit in 63 bits), and shows each column's worst: a cheap hash can
   spread i << 46 and still cluster at another shift. The tuples (i << 64, 0) hold promoting ints
   past 64 bits (descriptor J, the compiler's bigints.held), whose slots all hold -2**63: they
   spread only where the hash reads the ints' values. It checks the values, the insertion order
   and the deletions on the way. The counts depend on nothing but the runtime, so they are the
   same on every machine, and the run fails if a pattern averages more than LIMIT slots per
   lookup: a hash that behaved randomly would average at most 1.5 per miss and 2 per lookup
   after the deletions, at the fullest table (a third of the slots in use). The times
   (nanoseconds per insertion or hit, best of three) are for information only.
   The string-cache check counts calls/bytes through the real runtime.py hash, so repeated
   lookups must not rescan bytes. The Any-keys check counts the keys that dkeyeq compares
   (DICT_KEYEQ): a dict[Any, ...] finds a boxed str or int key through another box of an equal
   value without it, hashing each probe str once (#780), while 1.0 and True, equal to a key 1 of
   another type, still take it. The storage check reads the kinds of the tables from the page
   map: the collector never scans the key arrays of dicts and sets of ints, and scans those of
   strs, tuples and objects (P000: hashed by identity; H000: by their class, whose dicts have
   CPython's index, KTAG) and every dict's values, and the 8 slots of a new set whatever its kind
   (the compiler may change the kind of an empty set); so ints that are the addresses of strs
   nothing else holds keep none of them alive (#210), and objects that are keys or elements stay.
   Integer queries in Any dictionaries also check the allocation-free guarded probe,
   including identical probe counts and fallback before any user comparison.
   --hash-cache runs only these checks, also under GC stress.
   runtime.c's dict hash functions are in runtime.py, so the build links its IR (pystachy rt).
   usage: make dictprobe   (build/dictprobe [N...] or build/dictprobe --hash-cache) */
#include <time.h>
static long long dict_slots;          /* (not a name the runtime's code uses: the set's lookups have a local probes) */
#define DICT_PROBE() (dict_slots++)
static long long dict_keyeqs;
#define DICT_KEYEQ() (dict_keyeqs++)
#define pys_hash_str counted_hash_str
#include "../runtime.c"
#undef pys_hash_str

I pys_hash_str(Str *s);
static I hash_calls, hash_bytes;
static Str *zero_hash_key;
I counted_hash_str(Str *s) {
  hash_calls++; hash_bytes += s->len;
  /* Exercise the rare zero-result sentinel branch without changing the production hash. */
  return s == zero_hash_key ? 0 : pys_hash_str(s);
}

#define LIMIT 3.0
/* the programs' callbacks, which objects hashed by identity (P000) never call; an H000 object of
   the storage check (skey) hashes as its int field, which its __eq__ compares (c < 0: hash(a)) */
static I int_guard_calls, int_guard_hashes, int_guard_seen;
I pys_obj_eq(I c, I a, I b) {
  if (c == -92) { int_guard_hashes++; return 1000; }
  return c < 0 ? ((I *)a)[1] * 7 : a == b || ((I *)a)[1] == ((I *)b)[1];
}
I pys_obj_cmp(I c, I op, I a, I b) {
  if (c == -92) { int_guard_calls++; int_guard_seen = b; return 0; }
  (void)op; return a < b ? -1 : a > b;
}
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static const char *pats[] = {"i", "-i", "i << 46", "i << 32", "i * 1000", "(i // 128) << 32 | i % 128",
  "random", "f\"k{i}\"", "f\"{i:08}\"", "\"x\" * 64 + str(i)", "str(i) + \"x\" * 64", "letter case of i's bits",
  "objects, by identity", "(i << 64, 0): promoting ints", "i << s, -(i << s): s <= 56"};
#define NPAT (I)(sizeof pats / sizeof *pats - 1)   /* the last one is the sweep's */
#define MAXN 65536                     /* 2N keys i << 46 fit in 63 bits */
static List *keys;                     /* the collector's roots */
static Dict *dict;
static I *roots[] = {(I *)&keys, (I *)&dict};
static long long longest;
static int shift, sign;                /* the sweep's keys: sign * (i << shift) */
static double worst;                   /* the highest average, and how many are above LIMIT */
static I fails;

static _Noreturn void cache_bad(const char *what) { fprintf(stderr, "dictprobe: string cache: %s\n", what); exit(1); }
static void hash_count(I calls, I bytes) {
  if (hash_calls != calls || hash_bytes != bytes) {
    fprintf(stderr, "dictprobe: string cache: expected %lld calls/%lld bytes, got %lld/%lld\n",
            (long long)calls, (long long)bytes, (long long)hash_calls, (long long)hash_bytes);
    exit(1);
  }
}
static Str *cache_key(const char *s, I n) {
  Str *k = pys_str(s, n);
  if (k->dict_hash) cache_bad("new string has a populated cache");
  pys_list_append(keys, (I)k);
  return k;
}
static void hash_cache(void) {
  char text[4096]; memset(text, 'x', sizeof text);
  keys = pys_list_new(80);
  Str *a = cache_key(text, sizeof text), *equal = cache_key(text, sizeof text);
  text[sizeof text - 1] = 'y'; Str *b = cache_key(text, sizeof text);
  text[sizeof text - 1] = 'z'; Str *missing = cache_key(text, sizeof text);
  dict = pys_dict_new(1, 0);
  hash_calls = hash_bytes = 0;
  pys_dict_set(dict, (I)a, 7);
  hash_count(1, sizeof text);
  if (a->dict_hash != (uint64_t)pys_hash_str(a) || equal->dict_hash) cache_bad("hash value or per-object cache");
  pys_dict_set(dict, (I)b, 9);
  for (I i = 0; i < 100; i++) {
    if (pys_dict_get(dict, (I)(i % 2 ? b : a), -1) != (i % 2 ? 9 : 7) ||
        pys_dict_get(dict, (I)equal, -1) != 7 || pys_dict_has(dict, (I)missing)) cache_bad("hit/miss lookup");
  }
  hash_count(4, 4 * sizeof text);
  if (a == equal || a->dict_hash != equal->dict_hash) cache_bad("equal distinct strings");

  I bytes = hash_bytes;
  for (I i = 0; i < 64; i++) {
    char s[24]; I n = snprintf(s, sizeof s, "resize-%lld", (long long)i);
    Str *k = cache_key(s, n); pys_dict_set(dict, (I)k, i); bytes += n;
  }
  hash_count(68, bytes);
  for (I i = 0; i < 64; i++) if (pys_dict_pop(dict, keys->a[4 + i]) != i) cache_bad("resize/delete");
  if (pys_dict_pop(dict, (I)equal) != 7 || pys_dict_has(dict, (I)a)) cache_bad("equal-key deletion");
  pys_dict_set(dict, (I)a, 11);
  if (pys_dict_get(dict, (I)equal, -1) != 11) cache_bad("reinsertion");
  hash_count(68, bytes);

  /* Both the stored tuple and fresh equal tuples reuse each string component's cache. */
  dict = pys_dict_new((I)cstr("T2ss"), 0);
  I *pair = pys_alloc(16); pair[0] = (I)a; pair[1] = (I)b; pys_list_append(keys, (I)pair);
  pys_dict_set(dict, (I)pair, 13);
  for (I i = 0; i < 100; i++) {
    I *query = pys_alloc(16); query[0] = (I)equal; query[1] = (I)b;
    if (pys_dict_get(dict, (I)query, -1) != 13) cache_bad("tuple lookup");
  }
  hash_count(68, bytes);

  zero_hash_key = cache_key("forced-zero", 11);
  dict = pys_dict_new(1, 0);
  pys_dict_set(dict, (I)zero_hash_key, 17);
  if (zero_hash_key->dict_hash != 1) cache_bad("zero hash is not normalized before caching");
  for (I i = 0; i < 100; i++) if (pys_dict_get(dict, (I)zero_hash_key, -1) != 17) cache_bad("normalized hash lookup");
  hash_count(69, bytes + 11);
  zero_hash_key = 0;
  printf("string cache: one hash per string, cached hits/misses/tuples, zero hash normalized\n");
}

/* dict[Any, ...] (descriptor A): its keys are boxes, each probe here a new box of a new str or of
   an int above the small ints, so none is found as itself */
static _Noreturn void any_bad(const char *what) { fprintf(stderr, "dictprobe: Any keys: %s\n", what); exit(1); }
/* Exact lazy boxes share existing objects, including NaNs, without allocation.
   Missing boxes preserve integer limits and all float payload bits. The existing
   --hash-cache GC-stress run executes these checks too. */
static void numeric_boxes(void) {
  I ints[] = {-5, 0, 256, 257, -1000, INT64_MIN, INT64_MAX};
  uint64_t bits[] = {0, UINT64_C(0x8000000000000000), UINT64_C(0x7ff8000000000001), UINT64_C(0xfff8000000000002)};
  keys = pys_list_new(16);
  for (I i = 0; i < (I)(sizeof ints / sizeof *ints); i++) {
    Dyn *box = pys_dyn_int_box(ints[i], NULL);
    pys_list_append(keys, (I)box);
    if (box->t != &pys_dyntype_int || box->v != ints[i]) any_bad("lazy integer box value");
    I tick = gc_tick;
    for (I j = 0; j < 8; j++) if (pys_dyn_int_box(ints[i], box) != box) any_bad("lazy integer box identity");
    if (gc_tick != tick) any_bad("cached integer box allocates");
  }
  for (I i = 0; i < (I)(sizeof bits / sizeof *bits); i++) {
    double value; memcpy(&value, &bits[i], 8);
    Dyn *box = pys_dyn_float_box(value, NULL);
    pys_list_append(keys, (I)box);
    if (box->t != &pys_dyntype_float || (uint64_t)box->v != bits[i]) any_bad("lazy float box bits");
    I tick = gc_tick;
    for (I j = 0; j < 8; j++) if (pys_dyn_float_box(value, box) != box) any_bad("lazy float box identity");
    if (gc_tick != tick) any_bad("cached float box allocates");
    Dyn *fresh = pys_dyn_float_box(value, NULL);
    if (fresh == box || (uint64_t)fresh->v != bits[i]) any_bad("distinct float box or bits");
  }
  printf("Any numeric boxes: exact payloads, shared identities, no cached allocations\n");
}

static Str *any_str(I i) { char s[24]; I n = snprintf(s, sizeof s, "any-%lld", (long long)i); return pys_str(s, n); }
static void any_keys(void) {
  dict = pys_dict_new((I)cstr("A"), 0);
  for (I i = 0; i < 64; i++) { pys_dict_set(dict, (I)dstr(any_str(i)), i); pys_dict_set(dict, (I)pys_dyn_int(1000 + i), 100 + i); }
  if (!(dict->kind & KTAG) || dict->len != 128) any_bad("the table");
  dict_keyeqs = 0; hash_calls = 0;
  for (I r = 0; r < 2; r++)
    for (I i = 0; i < 64; i++)
      if (pys_dict_get(dict, (I)dstr(any_str(i)), -1) != i || pys_dict_get(dict, (I)pys_dyn_int(1000 + i), -1) != 100 + i ||
          pys_dict_has(dict, (I)dstr(any_str(64 + i))) || pys_dict_has(dict, (I)pys_dyn_int(2000 + i))) any_bad("a lookup");
  if (dict_keyeqs) any_bad("a boxed str or int key was compared by dkeyeq");
  if (hash_calls != 4 * 64) any_bad("a probe str was hashed more than once");
  pys_dict_set(dict, (I)pys_dyn_int(1), 1);
  if (pys_dict_get(dict, (I)pys_dyn_float(1.0), -1) != 1 || pys_dict_get(dict, (I)dbool(1), -1) != 1) any_bad("1.0 or True");
  if (!dict_keyeqs) any_bad("1.0 and True were not compared by dkeyeq");
  printf("Any keys: boxed strs and ints found without dkeyeq, one hash per probe str; 1.0 and True take it\n");
}

/* No allocation on hits, misses or fallback, even in the allocator's already-filled
   freelists (gc_allocd alone counts batches and would miss such an allocation). */
static I int_nobox(I value) {
  W *before[NK], *stress_before[NK];
  memcpy(before, fl, sizeof before); memcpy(stress_before, sfl, sizeof stress_before);
  I allocated = gc_allocd, collections = gc_n, ticks = gc_tick;
  Dict saved = *dict;
  I found = pys_dict_find_int_nobox(dict, value);
  if (memcmp(before, fl, sizeof before) || memcmp(stress_before, sfl, sizeof stress_before) ||
      allocated != gc_allocd || collections != gc_n || ticks != gc_tick) any_bad("integer probe allocated");
  if (memcmp(&saved, dict, sizeof saved)) any_bad("integer probe mutated the table");
  return found;
}

static void int_queries(void) {
  I vals[] = {0, 1, -1, -2, 1000, 1008, 1016, 1024, INT64_MIN, INT64_MAX,
              ((I)1 << 61) - 1, ((I)1 << 61), -((I)1 << 61)};
  I n = sizeof vals / sizeof *vals;
  dict = pys_dict_new((I)cstr("A"), 0);
  if (int_nobox(1000) != -1) any_bad("empty integer probe");
  keys = pys_list_new(n);
  for (I i = 0; i < n; i++) {
    Dyn *key = i < 2 ? dbool(i) : pys_dyn_int(vals[i]);
    pys_list_append(keys, (I)key); pys_dict_set(dict, (I)key, 100 + i);
  }
  for (I deleted = 0; deleted < 2; deleted++) {
    for (I i = 0; i < n; i++) {
      dict_slots = 0;
      I expected = pys_dict_find(dict, keys->a[i]), slots = dict_slots;
      dict_slots = 0; dict_keyeqs = 0;
      if (int_nobox(vals[i]) != expected || dict_slots != slots || dict_keyeqs) any_bad("integer hit/hole probes");
    }
    if (!deleted) for (I i = 0; i < n; i += 2) pys_dict_pop(dict, keys->a[i]);
  }
  for (I i = 2000; i < 2010; i++) if (int_nobox(i) != -1) any_bad("integer miss");

  /* An equal float must fall back, including its numeric hash's zero case. */
  dict = pys_dict_new((I)cstr("A"), 0);
  pys_dict_set(dict, (I)pys_dyn_float(0.0), 7);
  if (int_nobox(0) != -2) any_bad("float fallback");

  /* A colliding user key comes before the integer. The guarded probe must stop
     there without callbacks; the normal fallback observes the original query. */
  DSTR(desc, "O091"); DSTR(name, "IntProbeKey");
  static const DynType type = {DK_OBJ, (Str *)&desc, (Str *)&name, 91, 0, DF_HASH | DF_X, NULL, NULL, NULL};
  dict = pys_dict_new((I)cstr("A"), 0);
  Dyn *object = pys_dyn_ref(&type, (void *)1);
  pys_dict_set(dict, (I)object, 9);
  Dyn *query = pys_dyn_int(1000);
  pys_list_append(keys, (I)query);
  pys_dict_set(dict, (I)query, 11);
  int_guard_calls = int_guard_hashes = int_guard_seen = 0;
  dict_keyeqs = 0;
  if (int_nobox(1000) != -2 || int_guard_calls || int_guard_hashes || dict_keyeqs) any_bad("callback before fallback");
  I e = pys_dict_find(dict, (I)query);
  /* Hash 1000 in eight slots probes 0, 0, 1: the colliding object is compared
     twice, as CPython's perturb sequence requires, before the integer hit. */
  if (e < 0 || pys_dict_val(dict, e) != 11 || int_guard_calls != 2 || int_guard_hashes || int_guard_seen != (I)query)
    any_bad("fallback lost query identity or comparison order");
  printf("Any integer probes: no allocations, unchanged slots, guarded fallback preserves query identity\n");
}

#define MIB ((I)1 << 20)
static _Noreturn void storage_bad(const char *what) { fprintf(stderr, "dictprobe: storage: %s\n", what); exit(1); }
static int atomic(const void *p) {     /* is p's object one the collector never scans */
  uintptr_t w = (uintptr_t)p; Seg **m = pmap[w >> 30], *s = m ? m[w >> 12 & 0x3ffff] : 0;
  if (!s) storage_bad("a table outside the heap");
  return s->k & 1;                     /* (a chunk's free list 2 * class + atomic; a large object's: atomic) */
}
static void dict_kinds(Dict *d, int ints, const char *how) {
  if (atomic(d->keys) != ints || atomic(d->vals) || !atomic(d->hs) || !atomic(d->idx)) storage_bad(how);
}
static void set_kinds(Set *s, int ints, const char *how) {
  if (atomic(s->keys) != ints || !atomic(s->hs)) storage_bad(how);
}
static I skey(I kind, I i) {           /* key i of a dict or set of kind 0 (ints), 1 (strs), 2 (T2si), 3 (P000) or 4 (H000) */
  char b[24]; Str *s = pys_str(b, snprintf(b, sizeof b, "k%lld", (long long)i));
  if (kind < 2) return kind ? (I)s : i;
  I *t = pys_alloc(16); t[0] = (I)s; t[1] = i; return (I)t;   /* (a tuple, or an object of two fields) */
}
static Str *big(I i) {                 /* a str of 1 MiB, an object of its own; its first byte tells i */
  Str *s = pys_str_mul(cstr("x"), MIB); s->s[0] = (char)('a' + i); return s;
}
__attribute__((noinline)) static void addresses(void) {   /* ints that are the addresses of strs: keys, elements */
  Dict *d = pys_dict_new(0, 0); Set *s = pys_set_new(0); List *h = pys_list_new(16);
  keys = pys_list_new(4); keys->a[0] = (I)d; keys->a[1] = (I)s; keys->a[2] = (I)h; keys->len = 3;
  for (I i = 0; i < 16; i++) { I a = (I)big(i); pys_list_append(h, a); pys_dict_set(d, a, i); pys_set_add(s, a); }
  keys->a[2] = 0; keys->len = 2;       /* (h kept the strs apart, so that the 16 addresses differ; now nothing holds them) */
}
__attribute__((noinline)) static void held(void) {        /* strs that are keys, elements, values, tuple items, objects */
  Dict *ds = pys_dict_new(1, 0), *dv = pys_dict_new(0, 0), *dt = pys_dict_new((I)cstr("T2si"), 0), *dp = pys_dict_new((I)cstr("P000"), 0);
  Set *ss = pys_set_new(1), *sk = pys_set_new(0), *sp = pys_set_new((I)cstr("P000"));
  sk->kind = 1;                        /* (made of ints, then of strs: the compiler's typed_empty) */
  keys = pys_list_new(7); keys->a[0] = (I)ds; keys->a[1] = (I)dv; keys->a[2] = (I)dt; keys->a[3] = (I)ss; keys->a[4] = (I)sk;
  keys->a[5] = (I)dp; keys->a[6] = (I)sp; keys->len = 7;
  for (I i = 0; i < 40; i++) {         /* objects (4 strs, then fresh ones) in tables that grew: by identity */
    I o = i < 4 ? (I)big(20 + i) : (I)pys_alloc(16);
    pys_dict_set(dp, o, i < 4 ? 20 + i : -1); pys_set_add(sp, o);
  }
  for (I i = 0; i < 20; i++) {
    Str *x = big(i);
    if (i >= 16) pys_set_add(sk, (I)x);  /* (4 of them: its 8 slots, not a table of strs it grew) */
    else if (i % 4 == 0) pys_dict_set(ds, (I)x, i);
    else if (i % 4 == 1) pys_dict_set(dv, i, (I)x);
    else if (i % 4 == 2) { I *t = pys_alloc(16); t[0] = (I)x; t[1] = i; pys_dict_set(dt, (I)t, i); }
    else pys_set_add(ss, (I)x);
  }
}
__attribute__((noinline)) static void scrub_collect(void) {
  volatile I pad[4096];                /* erase conservative roots in the dead allocation frames */
  for (I i = 0; i < 4096; i++) pad[i] = 0;
  collect();
  if (pad[0]) storage_bad("scrub");
}
static void big_ok(Str *s, I i) { if (s->len != MIB || s->s[0] != 'a' + i || s->s[MIB - 1] != 'x') storage_bad("a kept str changed"); }
static void storage(void) {
  for (I kind = 0; kind < 5; kind++) { /* every path that makes a table: of ints, strs, tuples, then objects */
    I k2 = kind < 2 ? kind : (I)cstr(kind == 2 ? "T2si" : kind == 3 ? "P000" : "H000"); int ints = kind == 0;
    keys = pys_list_new(4);
    dict = pys_dict_new(k2, 10); keys->a[0] = (I)dict; keys->len = 1;
    dict_kinds(dict, ints, "a presized dict");
    for (I i = 0; i < 100; i++) pys_dict_set(dict, skey(kind, i), i);
    dict_kinds(dict, ints, "a dict that grew");
    dict_kinds(pys_dict_copy(dict), ints, "dict.copy()");
    dict_kinds(pys_dict_from(dict), ints, "dict(d)");
    for (I i = 0; i < 100; i += 2) pys_dict_pop(dict, kind == 3 ? dict->keys[i] : skey(kind, i));   /* (P000: an object is found as itself) */
    Dict *c = pys_dict_copy(dict);
    dict_kinds(c, ints, "dict.copy() of a dict with holes");
    if ((kind == 4) != ((dict->kind & KTAG) != 0) || (c->kind & KTAG) != (dict->kind & KTAG)) storage_bad("KTAG");
    for (I i = 1; i < 100; i += 2) if (pys_dict_get(c, kind == 3 ? dict->keys[i] : skey(kind, i), -1) != i) storage_bad("a key of a copy not found");
    pys_dict_clear(dict); pys_dict_set(dict, skey(kind, 1), 1);
    dict_kinds(dict, ints, "a dict filled again after clear()");
    Set *s = pys_set_new(k2); keys->a[1] = (I)s; keys->len = 2;
    set_kinds(s, 0, "a new set (its 8 slots are scanned: typed_empty may give it another kind)");
    for (I i = 0; i < 100; i++) pys_set_add(s, skey(kind, i));
    set_kinds(s, ints, "a set that grew");
    set_kinds(pys_set_copy(s), ints, "set.copy()");
  }
  /* Dynamic programs mark native builtin dict kinds for Python hash/probes.
     The marker must not turn integer payloads into conservative GC roots. */
  for (I kind = 0; kind < 2; kind++) {
    Dict *d = pys_dict_new((I)cstr(kind ? "!s" : "!i"), 10);
    dict_kinds(d, !kind, "a marked presized dict");
    for (I i = 0; i < 100; i++) pys_dict_set(d, skey(kind, i), i);
    dict_kinds(d, !kind, "a marked dict that grew");
    for (I i = 1; i < 100; i += 2) pys_dict_pop(d, skey(kind, i));
    Dict *c = pys_dict_copy(d), *f = pys_dict_from(d);
    dict_kinds(c, !kind, "a marked copy with holes");
    dict_kinds(f, !kind, "a marked constructor with holes");
    if (!(d->kind & KTAG) || c->len != 50 || f->len != 50 || pys_dict_getitem(c, skey(kind, 0)) != 0) storage_bad("marked live zero/copy");
    pys_dict_clear(d); pys_dict_set(d, skey(kind, 0), 0);
    dict_kinds(d, !kind, "a marked dict filled after clear");
  }
  addresses(); scrub_collect(); scrub_collect();
  if (gc_live >= 4 * MIB) storage_bad("ints that are the addresses of strs kept them alive");
  Dict *d = (Dict *)keys->a[0]; Set *s = (Set *)keys->a[1];
  if (d->len != 16 || s->len != 16) storage_bad("int keys lost");
  for (I e = 0; e < d->n; e++) if (!pys_dict_has(d, d->keys[e]) || !pys_set_has(s, d->keys[e])) storage_bad("an int key not found");
  held(); scrub_collect(); scrub_collect();
  if (gc_live < 24 * MIB) storage_bad("a str that is a key, element, value, tuple item or object key was freed");
  Dict *ds = (Dict *)keys->a[0], *dv = (Dict *)keys->a[1], *dt = (Dict *)keys->a[2]; Set *ss = (Set *)keys->a[3], *sk = (Set *)keys->a[4];
  Dict *dp = (Dict *)keys->a[5]; Set *sp = (Set *)keys->a[6];
  dict_kinds(dp, 0, "a dict of objects"); set_kinds(sp, 0, "a set of objects");
  if (dp->len != 40 || sp->len != 40) storage_bad("object keys lost");
  for (I e = 0; e < 4; e++) {
    big_ok((Str *)dp->keys[e], dp->vals[e]);
    if (!pys_set_has(sp, dp->keys[e]) || pys_dict_get(dp, dp->keys[e], -2) != 20 + e) storage_bad("an object key not found");
  }
  for (I e = 0; e < ds->n; e++) big_ok((Str *)ds->keys[e], ds->vals[e]);
  for (I e = 0; e < dv->n; e++) big_ok((Str *)dv->vals[e], dv->keys[e]);
  for (I e = 0; e < dt->n; e++) big_ok((Str *)((I *)dt->keys[e])[0], dt->vals[e]);
  I n = 0;
  for (I j = 0; j <= ss->mask; j++) if (ss->hs[j] != -1) { Str *x = (Str *)ss->keys[j]; big_ok(x, x->s[0] - 'a'); n++; }
  for (I j = 0; j <= sk->mask; j++) if (sk->hs[j] != -1) { Str *x = (Str *)sk->keys[j]; big_ok(x, x->s[0] - 'a'); n++; }
  if (sk->mask != 7 || ds->len + dv->len + dt->len + n != 20) storage_bad("kept strs lost");
  keys = 0; dict = 0;
  printf("storage: the key tables of ints are never scanned; those of strs, tuples and objects, and pys_dict_new's values, are\n");
}
static void val_kinds(Dict *d, int nums, const char *how) {
  if (atomic(d->vals) != nums || !atomic(d->hs) || !atomic(d->idx)) storage_bad(how);
}
__attribute__((noinline)) static void value_addresses(void) {   /* the addresses of 16 strs, values of a dict of ints only */
  Dict *d = pys_dict_new_atomic(1, 0); List *h = pys_list_new(16);
  keys = pys_list_new(2); keys->a[0] = (I)d; keys->a[1] = (I)h; keys->len = 2;
  for (I i = 0; i < 16; i++) { I a = (I)big(i); pys_list_append(h, a); pys_dict_set(d, skey(1, i), a); }
  keys->a[1] = 0; keys->len = 1;       /* (h kept the strs apart; now nothing scanned holds them) */
}
/* the value arrays of pys_dict_new_atomic's dicts (the compiler's dicts of ints, floats and bools)
   are atomic, through every path that makes one; pys_dict_new's are scanned */
static void values(void) {
  for (I kind = 0; kind < 2; kind++) {
    keys = pys_list_new(4);
    Dict *a = pys_dict_new_atomic(kind, 10), *s = pys_dict_new(kind, 10), *u = pys_dict_new_atomic(kind, 0);
    keys->a[0] = (I)a; keys->a[1] = (I)s; keys->a[2] = (I)u; keys->len = 3;
    val_kinds(a, 1, "a presized dict of numbers"); val_kinds(s, 0, "a presized dict");
    for (I i = 0; i < 100; i++) { pys_dict_set(a, skey(kind, i), i * 3); pys_dict_set(s, skey(kind, i), i * 3); }
    val_kinds(a, 1, "a dict of numbers that grew"); val_kinds(s, 0, "a dict that grew");
    val_kinds(pys_dict_copy(a), 1, "dict.copy() of numbers"); val_kinds(pys_dict_from(a), 1, "dict(d) of numbers");
    val_kinds(pys_dict_copy(s), 0, "dict.copy()"); val_kinds(pys_dict_from(s), 0, "dict(d)");
    pys_dict_update(u, a); val_kinds(u, 1, "an empty dict of numbers updated (a clone of the table)");
    for (I i = 0; i < 100; i += 2) pys_dict_pop(a, skey(kind, i));
    val_kinds(pys_dict_copy(a), 1, "dict.copy() of numbers with holes"); val_kinds(pys_dict_from(a), 1, "dict(d) of numbers with holes");
    val_kinds(pys_dict_fromkeys_dict(a, 0), 0, "dict.fromkeys(d, v)");   /* (v's type is not the values') */
    if (!atomic(pys_dict_values(a)->a) || atomic(pys_dict_values(s)->a)) storage_bad("values() as a list");
    scrub_collect();
    for (I i = 1; i < 100; i += 2) if (pys_dict_get(a, skey(kind, i), -1) != i * 3) storage_bad("a value lost");
    pys_dict_clear(a); pys_dict_set(a, skey(kind, 1), 1);
    val_kinds(a, 1, "a dict of numbers filled again after clear()");
  }
  value_addresses(); scrub_collect(); scrub_collect();
  if (gc_live >= 4 * MIB) storage_bad("int values that are the addresses of strs kept them alive");
  if (((Dict *)keys->a[0])->len != 16) storage_bad("the addresses' dict lost");
  keys = 0;
  printf("values: the value arrays of dicts of numbers are never scanned, also in their copies; other dicts' are\n");
}

#define X64 "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
static I key(I p, I i) {               /* key i of pattern p; the 2N keys of a pattern are distinct */
  char b[96]; uint64_t z;
  switch (p) {
  case 0: return i;
  case 1: return -i;
  case 2: return i << 46;
  case 3: return i << 32;
  case 4: return i * 1000;
  case 5: return (i / 128) << 32 | i % 128;
  case 6: z = (uint64_t)i * 0x9E3779B97F4A7C15ULL + 1;   /* SplitMix64: distinct for distinct i */
    z = (z ^ z >> 30) * 0xBF58476D1CE4E5B9ULL; z = (z ^ z >> 27) * 0x94D049BB133111EBULL; return (I)(z ^ z >> 31);
  case 7: return (I)pys_str(b, snprintf(b, sizeof b, "k%lld", (long long)i));
  case 8: return (I)pys_str(b, snprintf(b, sizeof b, "%08lld", (long long)i));
  case 9: return (I)pys_str(b, snprintf(b, sizeof b, "%s%lld", X64, (long long)i));
  case 10: return (I)pys_str(b, snprintf(b, sizeof b, "%lld%s", (long long)i, X64));
  case 12: { I *o = pys_alloc(24); o[0] = i; return (I)o; }   /* (an object of three fields: P000) */
  case 13: {   /* a tuple of promoting ints (T2Ji, the compiler's bigints.held): past 64 bits, -2**63 and its Mpz in slot 2 */
    Big b = pys_big_op(i, NULL, 64, NULL, 8); I *t = pys_alloc(24);
    t[0] = b.hi ? INT64_MIN : b.lo; t[2] = (I)b.hi; return (I)t;
  }
  case 14: return sign * (i << shift);
  default: for (int j = 0; j < 20; j++) b[j] = (char)('a' + j - (i >> j & 1) * 32);   /* "aBcD..." */
    return (I)pys_str(b, 20);
  }
}
static I lookup(I k, I dflt) {         /* d.get(k, dflt), noting the longest lookup */
  long long b = dict_slots; I v = pys_dict_get(dict, k, dflt);
  if (dict_slots - b > longest) longest = dict_slots - b;
  return v;
}
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static _Noreturn void bad(I p, I n, const char *what) { fprintf(stderr, "dictprobe: %s, %lld keys: %s\n", pats[p], (long long)n, what); exit(1); }
static double run(I p, I n, long long c[4]) {  /* c: slots visited by insert, hit, miss, deleted */
  double t = 1e9;
  for (int r = 0; r < 3; r++) {
    dict = pys_dict_new(p == 12 ? (I)cstr("P000") : p == 13 ? (I)cstr("T2Ji") : p >= 7 && p < NPAT, 0);
    dict_slots = 0; double t0 = now();
    for (I i = 0; i < n; i++) pys_dict_set(dict, keys->a[i], i);
    c[0] = dict_slots; dict_slots = 0;
    for (I i = 0; i < n; i++) if (lookup(keys->a[i], -1) != i) bad(p, n, "wrong value");
    if (now() - t0 < t) t = now() - t0;
    c[1] = dict_slots;
  }
  dict_slots = 0;
  for (I i = n; i < 2 * n; i++) if (lookup(keys->a[i], -1) != -1) bad(p, n, "absent key found");
  c[2] = dict_slots;
  for (I i = 0; i < n; i += 2) if (pys_dict_pop(dict, keys->a[i]) != i) bad(p, n, "wrong value popped");
  dict_slots = 0;
  for (I i = 0; i < n; i++) if (lookup(keys->a[i], -1) != (i % 2 ? i : -1)) bad(p, n, "deleted key found, or kept key lost");
  c[3] = dict_slots;
  I j = 1;                             /* the survivors, in insertion order */
  for (I e = pys_dict_next(dict, 0, n / 2, 0), k = 0; e >= 0; e = pys_dict_next(dict, e + 1, n / 2, ++k), j += 2)
    if (pys_dict_key(dict, e) != keys->a[j] || pys_dict_val(dict, e) != j) bad(p, n, "insertion order lost");
  if (j != n + 1) bad(p, n, "survivors lost");
  return t / (2 * n) * 1e9;
}
static void tally(long long c[4], I n) {   /* the limit applies to hits, misses and lookups after deletions */
  for (int m = 1; m < 4; m++) {
    if ((double)c[m] / n > worst) worst = (double)c[m] / n;
    if ((double)c[m] / n > LIMIT) fails++;
  }
}
int main(int argc, char **argv) {
  gc_init(__builtin_frame_address(0), roots, 2);
  hash_cache();
  any_keys();
  numeric_boxes();
  int_queries();
  storage();
  values();
  if (argc == 2 && !strcmp(argv[1], "--hash-cache")) return 0;
  I ns[8] = {4000, 8000, 16000, 30000}, nn = 4;
  if (argc > 1) for (nn = 0; nn + 1 < argc && nn < 8; nn++) ns[nn] = atoll(argv[nn + 1]) & ~(I)1;
  for (I k = 0; k < nn; k++) if (ns[k] < 2 || ns[k] > MAXN) { fprintf(stderr, "usage: dictprobe [N...]   (2 <= N <= %d)\n", MAXN); return 2; }
  for (int r = 0; r < 100; r++) {      /* the heap grows to its working size before the timings */
    dict = pys_dict_new(0, 0);
    for (I i = 0; i < 30000; i++) pys_dict_set(dict, i, i);
  }
  printf("%-28s %6s %7s %6s %6s %8s %8s %6s\n", "keys", "n", "insert", "hit", "miss", "deleted", "longest", "ns/op");
  for (I p = 0; p < NPAT; p++)
    for (I k = 0; k < nn; k++) {
      I n = ns[k]; long long c[4];
      keys = pys_list_new(2 * n);
      for (I i = 0; i < 2 * n; i++) keys->a[keys->len++] = key(p, i);
      longest = 0;
      double t = run(p, n, c);
      printf("%-28s %6lld %7.2f %6.2f %6.2f %8.2f %8lld %6.1f\n", pats[p], (long long)n, (double)c[0] / n,
             (double)c[1] / n, (double)c[2] / n, (double)c[3] / n, longest, t);
      tally(c, n);
    }
  double w[4] = {0}, t = 0; long long most = 0; int np = 0;
  for (shift = 0; shift <= 56; shift++)
    for (sign = 1; sign >= -1; sign -= 2, np++) {
      I n = shift < 50 ? 8000 : (I)1 << (62 - shift); long long c[4];
      keys = pys_list_new(2 * n);
      for (I i = 0; i < 2 * n; i++) keys->a[keys->len++] = key(NPAT, i);
      longest = 0;
      t += run(NPAT, n, c);
      if (longest > most) most = longest;
      for (int m = 0; m < 4; m++) if ((double)c[m] / n > w[m]) w[m] = (double)c[m] / n;
      tally(c, n);
    }
  printf("%-28s %6d %7.2f %6.2f %6.2f %8.2f %8lld %6.1f\n", pats[NPAT], 8000, w[0], w[1], w[2], w[3], most, t / np);
  printf("worst average: %.2f slots per lookup (limit %.1f)\n", worst, LIMIT);
  if (fails) fprintf(stderr, "dictprobe: %lld averages above %.1f slots per lookup\n", (long long)fails, LIMIT);
  return fails != 0;
}
