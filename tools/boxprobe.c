/* Boxes, a dynamic value's {DynType *, payload} and a closed union's {tag, payload}, take 16-byte
   slots exactly, without the byte of slack other objects get (gc_box, #800): scanned where the
   payload can be a reference (pys_dyn_ref, pys_ubox), atomic for an int's or a float's. A pointer
   to a box's payload word keeps the box, and the str it holds, alive across a collection. The
   negative control: a pointer one past a box's end is the next slot's, and keeps the box no more,
   so only objects that no code walks may go without the slack. Deterministic slot-size, kind and
   survival checks. Like listprobe, this includes the real runtime and links runtime.py's IR.
   usage: make boxprobe */
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static uintptr_t held;                /* the one word that refers to the box a check holds */
static Dyn *sibling;                  /* a live box of its chunk, and a live str of its str's chunk */
static I *roots[] = {(I *)&held, (I *)&sibling};
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

__attribute__((noinline)) static void sizes(void) {
  box_slot(pys_dyn_int(1000), 1, "an int's box is not in an atomic 16-byte slot");
  box_slot(pys_dyn_float(0.5), 1, "a float's box is not in an atomic 16-byte slot");
  box_slot(pys_dyn_ref(&pys_dyntype_str, cstr("s")), 0, "a str's box is not in a scanned 16-byte slot");
  box_slot(pys_ubox(3, 4), 0, "a union's box is not in a scanned 16-byte slot");
  Seg *s = gc_find(pys_alloc(16));
  if (!s || s->size != 24) bad("an object of 16 bytes that is not a box has no byte of slack");
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
  gc_init(__builtin_frame_address(0), roots, 2);
  sizes();
  uintptr_t x = hold(8);               /* the payload word's address */
  scrub_collect();
  alive(x);
  x = hold(16);                        /* one past the end: the next slot's address */
  scrub_collect();
  dead(x);
  puts("boxprobe: 16-byte box slots, a box kept by its payload word's address, and the one-past-the-end control passed");
  return 0;
}
