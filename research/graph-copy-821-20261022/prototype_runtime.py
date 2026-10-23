"""Write a candidate exact-int Any-dict lookup overlay; not yet validated.

Usage: python specialize_runtime.py INPUT_RUNTIME OUTPUT_RUNTIME [--hash]
No layout, storage, probing, identity or callback policy changes. A matching-hash
non-int stored key returns -2 so one common generic loop runs before callbacks.
--hash additionally removes the generic dyn-hash dispatch for int/bool keys and
is separate so its effect can be evaluated independently.
"""
from pathlib import Path
import sys


source = Path(sys.argv[1]).read_text()


def replace(old: str, new: str) -> None:
    global source
    assert source.count(old) == 1, (old, source.count(old))
    source = source.replace(old, new)


replace("static int dyn_keyeq(Dyn *a, Dyn *b);", """static int dyn_keyeq(Dyn *a, Dyn *b);
static int dyn_intkey(Dyn *a);""")
replace("__attribute__((noinline)) static I dfindc(Dict *d, I k, uint64_t h, I *free) { return dlook(d, k, h, free, d->size - 1, 2); }", """/* An exact int lookup in an Any table: all its earlier hash-matching int
   comparisons are pure. The first other type returns -2 for the generic lookup, so
   user comparisons run in the same order, with the original key box, and retain
   dlook's mutation/restart rules. The table's layout, hashes and probe sequence
   stay unchanged. */
static inline __attribute__((always_inline)) I dlook_int(Dict *d, I k, uint64_t h, I *free) {
  Dyn *key = (Dyn *)k; const DynType *type = key->t; I value = key->v;
  I f = -1; uint64_t m = d->size - 1;
  for (uint64_t i = h & m, p = h;; p >>= 5, i = (i * 5 + p + 1) & m) {
    DICT_PROBE();
    int32_t e = d->idx[i];
    if (!e) { if (free) *free = f < 0 ? (I)i : f; return -1; }
    if (e < 0) { if (f < 0) f = i; }
    else {
      I x = d->keys[e - 1];
      if (x == k) return i;
      if (d->hs[e - 1] == h) {
        Dyn *stored = (Dyn *)x;
        if (stored->t != type) return -2;
        if (stored->v == value) return i;
      }
    }
  }
}
__attribute__((noinline)) static I dfindc(Dict *d, I k, uint64_t h, I *free) {
  const char *s = kdesc(d->kind);
  if (*s == 'A' && !s[1] && dyn_intkey((Dyn *)k)) {
    I found = dlook_int(d, k, h, free);
    if (found != -2) return found;
  }
  return dlook(d, k, h, free, d->size - 1, 2);
}""")
replace("static int dnum(const Dyn *x) { return DKIND(x) == DK_INT || DKIND(x) == DK_BOOL; }", """static int dyn_intkey(Dyn *x) { return x->t == &pys_dyntype_int; }
static int dnum(const Dyn *x) { return DKIND(x) == DK_INT || DKIND(x) == DK_BOOL; }""")
if "--hash" in sys.argv:
    replace("static uint64_t hdyn(Dyn *x) { return (uint64_t)(DKIND(x) == DK_STR ? hstr((Str *)x->v) : pys_dyn_hash(x)); }", """static uint64_t hdyn(Dyn *x) {
  int kind = DKIND(x);
  return (uint64_t)(kind == DK_STR ? hstr((Str *)x->v) : kind == DK_INT || kind == DK_BOOL ? hint(x->v) : pys_dyn_hash(x));
}""")
Path(sys.argv[2]).write_text(source)
