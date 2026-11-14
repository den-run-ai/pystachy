/* Boxes, a dynamic value's {DynType *, payload} and a closed union's {tag, payload}, take 16-byte
   slots exactly, without the byte of slack other objects get (gc_box, #800): scanned where the
   payload can be a reference (pys_dyn_ref, pys_ubox), atomic for an int's or a float's. A pointer
   to a box's payload word keeps the box, and the str it holds, alive across a collection. The
   negative control: a pointer one past a box's end is the next slot's, and keeps the box no more,
   so only objects that no code walks may go without the slack. Deterministic slot-size, kind and
   survival checks. Like listprobe, this includes the real runtime and links runtime.py's IR.
   usage: make boxprobe */
#include "../runtime.c"
#include <stddef.h>

_Static_assert(offsetof(Dyn, t) == 0 && offsetof(Dyn, v) == 8, "dynamic payload ABI");
_Static_assert(offsetof(DynType, kind) == 0 && offsetof(DynType, cls) == 24 &&
               offsetof(DynType, base) == 32 && offsetof(DynType, flags) == 40, "dynamic descriptor ABI");

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static uintptr_t held;                /* the one word that refers to the box a check holds */
static Dyn *sibling;                  /* a live box of its chunk, and a live str of its str's chunk */
static List *sibling_list;            /* keeps the list chunk mapped for the atomic-box negative control */
static I *roots[] = {(I *)&held, (I *)&sibling, (I *)&sibling_list};
static const uintptr_t addr_xor = 0x5a5a5a5a5a5a5a5a;   /* an address xor this is not a root */
static _Noreturn void bad(const char *what) { fprintf(stderr, "boxprobe: %s\n", what); exit(1); }

__attribute__((noinline)) static void scrub_collect(void) {
  volatile I pad[4096];
  for (I i = 0; i < 4096; i++) pad[i] = 0;
  collect();
  if (pad[0]) bad("stack scrub");
}

static void box_slot(void *p, int atomic, const char *what) {
  Seg *s = gc_find(p);
  if (!s || s->large || s->size != 16 || (s->k & 1) != atomic) bad(what);
}

/* The exact payload bits and referenced address consumed by dyn.payload's
   LLVM load; guards establish which interpretation that word permits. */
__attribute__((noinline)) static void boxing_contracts(void) {
  const I integers[] = {INT64_MIN, -1000, -5, 0, 256, 1000, INT64_MAX};
  for (size_t i = 0; i < sizeof integers / sizeof *integers; i++) {
    Dyn *box = pys_dyn_int(integers[i]);
    if (box->t != &pys_dyntype_int || box->v != integers[i] ||
        pys_dyn_unbox(box, &pys_dyntype_int) != integers[i]) bad("int boxing changed payload bits");
  }
  const uint64_t floats[] = {0, UINT64_C(0x8000000000000000), UINT64_C(0x3ff8000000000000),
                            UINT64_C(0x7ff0000000000000), UINT64_C(0xfff0000000000000),
                            UINT64_C(0x7ff8000000000042)};
  for (size_t i = 0; i < sizeof floats / sizeof *floats; i++) {
    double value;
    memcpy(&value, &floats[i], 8);
    Dyn *box = pys_dyn_float(value);
    if (box->t != &pys_dyntype_float || (uint64_t)box->v != floats[i] ||
        (uint64_t)pys_dyn_unbox(box, &pys_dyntype_float) != floats[i]) bad("float boxing changed payload bits");
  }
  Str *value = cstr("same address");
  Dyn *box = pys_dyn_ref(&pys_dyntype_str, value);
  if (box->t != &pys_dyntype_str || (void *)box->v != value ||
      (void *)pys_dyn_unbox(box, &pys_dyntype_str) != value) bad("reference boxing copied its payload");
  if (pys_dyn_ref(&pys_dyntype_str, NULL) != DNONE) bad("null reference did not box None");
}

__attribute__((noinline)) static void sizes(void) {
  box_slot(pys_dyn_int(1000), 1, "an int's box is not in an atomic 16-byte slot");
  box_slot(pys_dyn_big(0, pys_mpz_from_str(cstr("1180591620717411303424"), 10)), 0,
           "a wide int's box is not in a scanned 16-byte slot");
  box_slot(pys_dyn_float(0.5), 1, "a float's box is not in an atomic 16-byte slot");
  box_slot(pys_dyn_ref(&pys_dyntype_str, cstr("s")), 0, "a str's box is not in a scanned 16-byte slot");
  box_slot(pys_ubox(3, 4), 0, "a union's box is not in a scanned 16-byte slot");
  Seg *s = gc_find(pys_alloc(16));
  if (!s || s->size != 24) bad("an object of 16 bytes that is not a box has no byte of slack");
}

/* The wrapper is the only retained route to the list and its scanned numeric
   companion after this frame returns. Check mutable aliases before collection,
   then remove the wrapper's trace edge in the atomic-allocation negative control. */
__attribute__((noinline)) static uintptr_t hold_list(int atomic) {
  for (I attempt = 0; attempt < 1000; attempt++) {
    List *list = pys_list_new_atomic(4);
    sibling_list = pys_list_new_atomic(4);
    if (gc_find(list) != gc_find(sibling_list)) continue;
    pys_list_append(list, 1000);
    Dyn *wrapper = pys_dyn_ref(&pys_dyntype_intlist, list);
    List *alias = (List *)pys_dyn_unbox(wrapper, &pys_dyntype_intlist);
    if (alias != list || alias->a != list->a || alias->ids != list->ids)
      bad("reference round trip changed a mutable alias");
    Dyn *item = pys_dyn_int(7000);
    pys_dyn_setitem(wrapper, pys_dyn_int(0), item);
    if (pys_list_get(alias, 0) != 7000 || pys_list_get_identity(alias, 0, 1) != item)
      bad("write through boxed alias did not reach the original list");
    pys_list_set(alias, 0, 8000);
    if (pys_dyn_getitem(wrapper, pys_dyn_int(0))->v != 8000)
      bad("write through typed alias did not reach the reference box");
    if (atomic) {
      Dyn *untraced = gc_box(1);
      untraced->t = wrapper->t; untraced->v = wrapper->v;
      wrapper = untraced;
    }
    held = (uintptr_t)wrapper;
    return (uintptr_t)list ^ addr_xor;
  }
  bad("no two lists in one chunk");
}

__attribute__((noinline)) static void list_state(uintptr_t encoded, int alive) {
  List *list = (List *)(encoded ^ addr_xor);
  if (alive) {
    if (list->len != 1 || list->a[0] != 8000 || !list->ids ||
        ((Dyn *)list->ids[1])->t != &pys_dyntype_int || ((Dyn *)list->ids[1])->v != 8000)
      bad("rooted reference box lost its mutable list or numeric companion");
  } else if (list->cap || list->a || list->ids) {
    bad("atomic reference box retained its otherwise unreachable list");
  }
}

/* A box of the str "payload" that only held refers to, at offset off from the box. The box and its
   str share their chunks with sibling's, so a collection sweeps both chunks (rather than pooling
   them), and a dead box's slot is zeroed but for the free list's link in its first word. Returns
   the box's address xor addr_xor, which the caller takes back only after a collection (in a
   function of its own, so that the compiler cannot do it earlier) */
__attribute__((noinline)) static uintptr_t hold(uintptr_t off) {
  for (I i = 0; i < 1000; i++) {
    Dyn *b = pys_dyn_ref(&pys_dyntype_str, cstr("payload"));
    sibling = pys_dyn_ref(&pys_dyntype_str, cstr("sibling"));
    if (gc_find(b) == gc_find(sibling) && gc_find((void *)b->v) == gc_find((void *)sibling->v)) {
      held = (uintptr_t)b + off;
      return (uintptr_t)b ^ addr_xor;
    }
  }
  bad("no two boxes in one chunk");
}

__attribute__((noinline)) static void alive(uintptr_t x) {
  Dyn *b = (Dyn *)(x ^ addr_xor);
  Str *s = (Str *)b->v;
  if (b->t != &pys_dyntype_str || !s || s->len != 7 || memcmp(s->s, "payload", 8))
    bad("a box that a pointer to its payload word refers to, or its str, was collected");
}

__attribute__((noinline)) static void dead(uintptr_t x) {
  Dyn *b = (Dyn *)(x ^ addr_xor);
  if (b->t == &pys_dyntype_str || b->v) bad("a box that only a pointer one past its end refers to survived");
}

int main(void) {
  gc_init(__builtin_frame_address(0), roots, 3);
  boxing_contracts();
  sizes();
  uintptr_t x = hold(8);               /* the payload word's address */
  scrub_collect();
  alive(x);
  x = hold(16);                        /* one past the end: the next slot's address */
  scrub_collect();
  dead(x);
  x = hold_list(0);
  scrub_collect();
  list_state(x, 1);
  x = hold_list(1);
  scrub_collect();
  list_state(x, 0);
  puts("boxprobe: boxing bits, mutable reference aliases, traced list companions, atomic-root negative control, 16-byte slots and one-past-the-end control passed");
  return 0;
}
