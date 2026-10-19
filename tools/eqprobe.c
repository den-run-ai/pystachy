/* A shared DAG must not be expanded into its exponential logical tree by
   equality, ordering or list searches. Count the real runtime's comparisons;
   abort after 64 so an unfixed runtime fails promptly, without a timing limit.
   Dicts and sets of objects hashed by identity (P<id> keys) compare without
   the program's equality, which an H<id> key's lookup calls only for a key of
   the same hash; neither hashes keys again to compare tables (pys_obj_eq(-1 - id, a, 0)
   is the hash: here, the first field's modulo 4). */
static void eq_probe(void);
#define EQ_PROBE() eq_probe()
#include "../runtime.c"

static I obj_eqs, obj_hashes;
I pys_obj_eq(I c, I a, I b) {
  if (c < 0) { obj_hashes++; return ((I *)a)[0] % 4; }
  obj_eqs++; return ((I *)a)[0] == ((I *)b)[0];
}
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static I comparisons, limit = 64;      /* (the objects below count no DAG) */
static _Noreturn void bad(const char *what) { fprintf(stderr, "eqprobe: %s\n", what); exit(1); }
static void eq_probe(void) { if (++comparisons > limit) bad("shared DAG traversed more than 64 comparisons"); }
static List *child, *left, *right, *haystack;
static Str *desc;
static void *uleft, *uright, *ualias;
static Dict *dleft, *dright;
static Set *sleft, *sright;
static I *roots[] = {(I *)&child, (I *)&left, (I *)&right, (I *)&haystack, (I *)&desc,
                    (I *)&uleft, (I *)&uright, (I *)&ualias, (I *)&dleft, (I *)&dright, (I *)&sleft, (I *)&sright};

int main(void) {
  gc_init(__builtin_frame_address(0), roots, 12);
  child = pys_list_new(1);
  pys_list_append(child, 7);
  for (int i = 0; i < 32; i++) {
    List *parent = pys_list_new(2);
    pys_list_append(parent, (I)child);
    pys_list_append(parent, (I)child);
    child = parent;
  }
  left = pys_list_copy(child);
  right = pys_list_copy(child);
  char d[35]; memset(d, 'L', 33); d[33] = 'i'; d[34] = 0;
  desc = cstr(d);
  if (!pys_eq((I)left, (I)right, desc)) bad("equal DAGs compare unequal");
  if (pys_cmpop((I)left, (I)right, desc, 0) || !pys_cmpop((I)left, (I)right, desc, 1) ||
      pys_cmpop((I)left, (I)right, desc, 2) || !pys_cmpop((I)left, (I)right, desc, 3)) bad("DAG ordering");
  haystack = pys_list_new(2);
  pys_list_append(haystack, (I)left);
  pys_list_append(haystack, (I)left);
  if (pys_list_find(haystack, (I)left, desc) != 0 || pys_list_find(haystack, (I)right, desc) != 0 ||
      pys_list_index(haystack, (I)right, desc, 0, 2) != 0 || pys_list_count(haystack, (I)right, desc) != 2)
    bad("DAG search");
  pys_list_remove(haystack, (I)right, desc);
  if (haystack->len != 1 || haystack->a[0] != (I)left) bad("DAG removal");
  comparisons = 0;
  char ud[64]; snprintf(ud, sizeof(ud), "U2:1:%s2:s", d);
  desc = cstr(ud);
  uleft = pys_ubox(1, (I)left); uright = pys_ubox(1, (I)right); ualias = pys_ubox(1, (I)left);
  if (!pys_eq((I)uleft, (I)uright, desc) || !pys_eq((I)uleft, (I)ualias, desc)) bad("boxed DAG equality");
  haystack = pys_list_new(2);
  pys_list_append(haystack, (I)uleft); pys_list_append(haystack, (I)uleft);
  if (pys_list_find(haystack, (I)ualias, desc) != 0 || pys_list_find(haystack, (I)uright, desc) != 0 ||
      pys_list_index(haystack, (I)uright, desc, 0, 2) != 0 || pys_list_count(haystack, (I)uright, desc) != 2)
    bad("boxed DAG search");
  pys_list_remove(haystack, (I)uright, desc);
  if (haystack->len != 1 || haystack->a[0] != (I)uleft) bad("boxed DAG removal");
  limit = (I)1 << 40;
  /* Named recursive descriptors use byte-relative edges rather than expanding
     a JSON-shaped type to the input's depth. The same boxes retain aliases. */
  desc = cstr("?U4:1:i2:s3:LR13:4:DsR21:");
  child = pys_list_new(3);
  pys_list_append(child, (I)pys_ubox(1, 7));
  pys_list_append(child, 0);
  pys_list_append(child, (I)pys_ubox(2, (I)cstr("text")));
  dleft = pys_dict_new(1, 0);
  pys_dict_set(dleft, (I)cstr("items"), (I)pys_ubox(3, (I)child));
  left = pys_list_new(1);
  pys_list_append(left, (I)pys_ubox(4, (I)dleft));
  dright = pys_dict_new(1, 0);
  pys_dict_set(dright, (I)cstr("items"), (I)pys_ubox(3, (I)pys_list_copy(child)));
  right = pys_list_new(1);
  pys_list_append(right, (I)pys_ubox(4, (I)dright));
  uleft = pys_ubox(3, (I)left); uright = pys_ubox(3, (I)right);
  if (!pys_eq((I)uleft, (I)uright, desc)) bad("recursive descriptor equality");
  if (strcmp(pys_repr((I)uleft, desc)->s, "[{'items': [7, None, 'text']}]") != 0) bad("recursive descriptor repr");
  pys_list_append(child, (I)pys_ubox(1, 8));
  if (pys_eq((I)uleft, (I)uright, desc)) bad("recursive descendant mutation lost");
  left = pys_list_new(1); uleft = pys_ubox(3, (I)left);
  pys_list_append(left, (I)uleft);
  if (strcmp(pys_repr((I)uleft, desc)->s, "[[...]]") != 0 || !pys_eq((I)uleft, (I)uleft, desc))
    bad("recursive cycle identity or repr");
  for (int h = 0; h < 2; h++) {        /* objects of field i: P000 by identity, H000 by i % 4 and their fields */
    I kind = (I)cstr(h ? "H000" : "P000");
    dleft = pys_dict_new(kind, 0); dright = pys_dict_new(kind, 0); sleft = pys_set_new(kind); sright = pys_set_new(kind);
    for (I i = 0; i < 16; i++) {
      I *o = pys_alloc(16); o[0] = i;
      pys_dict_set(dleft, (I)o, i); pys_set_add(sleft, (I)o);
    }
    for (I i = 15; i >= 0; i--) { pys_dict_set(dright, dleft->keys[i], i); pys_set_add(sright, dleft->keys[i]); }
    obj_eqs = obj_hashes = 0; comparisons = 0;
    if (!pys_eq((I)dleft, (I)dright, cstr(h ? "DH000i" : "DP000i")) || !pys_eq((I)sleft, (I)sright, cstr(h ? "SH000" : "SP000")))
      bad("dicts or sets of the same objects compare unequal");
    if (obj_hashes || (!h && obj_eqs)) bad("equal dicts or sets of objects hashed them again, or ran the program's equality for identity keys");
    I *other = pys_alloc(16); other[0] = 3;
    if (pys_dict_has(dleft, (I)other) != h || pys_set_has(sleft, (I)other) != h) bad("a lookup of an object found the wrong key");
    if (obj_hashes != 2 * h || (!h && obj_eqs)) bad("a lookup of an object ran the program's hash or equality where it should not");
  }
  puts("eqprobe: native and union-boxed shared DAG equality and searches passed within 64 comparisons each; objects compare by identity or by their hash");
  return 0;
}
