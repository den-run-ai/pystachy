/* Integration-contract probe for the opt-in BDWGC overlay.  Compile with
   -DPYSTACHY_GC_RUNTIME='"/absolute/overlay/runtime.c"' and the same dependency. */
#include PYSTACHY_GC_RUNTIME
#include <assert.h>

/* Language-level dispatch is not used by this C integration probe. */
I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static I *test_root;
static void **observed[5];            /* cells are atomic, so these are weak */
static void *watch(void *p, int i) {
  observed[i] = GC_malloc_atomic(sizeof(void *));
  assert(observed[i]);
  *observed[i] = p;
  assert(GC_general_register_disappearing_link(observed[i], p) == GC_SUCCESS);
  return p;
}

__attribute__((noinline)) static void make_roots(void) {
  unsigned char *p = watch(pys_alloc_atomic(64), 0);
  p[0] = 71; p[63] = 29;
  *test_root = (I)(p + 64);           /* only the one-past pointer is strong */
  protos = malloc(sizeof *protos);
  assert(protos);
  protos[0] = watch(pys_alloc_atomic(64), 1);
  nprotos = cprotos = 1;
  ((unsigned char *)protos[0])[11] = 83;
  unw = malloc(sizeof *unw);
  assert(unw);
  unw[0] = (Unwind){NULL, watch(pys_alloc_atomic(64), 2)};
  nunw = cunw = 1;
  ((unsigned char *)unw[0].arg)[13] = 97;
  void **holder = watch(pys_alloc(sizeof(void *)), 3);
  holder[0] = watch(pys_alloc_atomic(64), 4);
  ((unsigned char *)holder[0])[17] = 101;
  /* Retain this graph through an ordinary global slot reported to the GC. */
  test_root[1] = (I)holder;
}

__attribute__((noinline)) static void clear_roots(void) {
  test_root[0] = test_root[1] = 0;
  nprotos = nunw = 0;
}

__attribute__((noinline)) static void collect_clean(void) {
  volatile uintptr_t scrub[4096];
  for (size_t i = 0; i < sizeof scrub / sizeof *scrub; i++) scrub[i] = 0;
  GC_clear_stack(NULL);
  GC_gcollect();
  (void)scrub[0];
}

__attribute__((noinline)) static void check_roots(void) {
  for (int i = 0; i < 5; i++) assert(*observed[i]);
  unsigned char *p = (void *)(test_root[0] - 64);
  assert(p[0] == 71 && p[63] == 29);
  assert(((unsigned char *)protos[0])[11] == 83);
  assert(((unsigned char *)unw[0].arg)[13] == 97);
  void **holder = (void *)test_root[1];
  assert(((unsigned char *)holder[0])[17] == 101);
}

__attribute__((noinline)) static void zero_and_strings(void) {
  for (int i = 0; i < 10000; i++) {
    unsigned char *p = pys_alloc_atomic(65);
    for (int j = 0; j <= 65; j++) assert(!p[j]);
    memset(p, 0xcc, 66);
    p = pys_new(24);
    for (int j = 0; j <= 24; j++) assert(!p[j]);
    memset(p, 0xcc, 25);
  }
  List *ints = pys_list_new_atomic(0), *refs = pys_list_new(0);
  for (int i = 0; i < 2048; i++) {
    pys_list_append(ints, i);
    pys_list_append(refs, (I)cstr("retained"));
  }
  assert(atomic_items(ints->a) && !atomic_items(refs->a));
  List *copy = pys_list_copy(ints);
  assert(atomic_items(copy->a));
  pys_list_clear(copy);
  assert(atomic_items(copy->a));
  pys_list_append(copy, 19);
  assert(atomic_items(copy->a) && copy->a[0] == 19);
  Str *s = cstr("x"), *t = cstr("abc");
  for (int i = 0; i < 5000; i++) s = pys_str_iadd(s, t, 1);
  assert(s->len == 15001 && s->s[0] == 'x' && s->s[15000] == 'c' && !s->s[15001]);
  Str *alias = s;
  s = pys_str_iadd(s, t, 0);
  assert(alias != s && alias->len == 15001 && s->len == 15004);
}

/* Return from the allocation frame before provoking collection so that a
   fresh child is retained through the old holder, not a C local. */
__attribute__((noinline)) static void store_child(int i) {
  unsigned char *p = pys_alloc_atomic(4096);
  p[17] = (unsigned char)i;
  ((void **)test_root[1])[0] = p;
}

__attribute__((noinline)) static void churn(void) {
  GC_clear_stack(NULL);
  for (int j = 0; j < 20; j++) {
    unsigned char *trash = gc_raw(4096);
    trash[0] = (unsigned char)j;
    GC_reachable_here(trash);
  }
}

/* An old mutable scanned object repeatedly receives fresh objects. The
   incremental collector's own dirty-page machinery must preserve these edges;
   Pystachy does not emit barriers. */
__attribute__((noinline)) static void mutate(void) {
  for (int i = 0; i < 5000; i++) {
    store_child(i);
    churn();
    assert(((unsigned char *)((void **)test_root[1])[0])[17] == (unsigned char)i);
  }
}

int main(int argc, char **argv) {
  test_root = calloc(2, sizeof *test_root);
  assert(test_root);
  I *roots[2] = {test_root, test_root + 1};
  pys_init(argc, argv, __builtin_frame_address(0), roots, 2);
  if (argc > 1) {
    if (!strcmp(argv[1], "weakref")) pys_weakref_new(NULL, NULL);
    if (!strcmp(argv[1], "file")) pys_open(NULL, NULL, NULL, NULL, 0);
    if (!strcmp(argv[1], "track")) pys_track(NULL, 0, 0);
    if (!strcmp(argv[1], "extension")) pys_init_lib(NULL, 0);
    return 99;
  }
  make_roots();
  for (int i = 0; i < 4; i++) collect_clean();
  check_roots();
  mutate();
  zero_and_strings();
  clear_roots();
  for (int i = 0; i < 8; i++) collect_clean();
  /* The prototype/cleanup entries past their live counts must not retain
     objects. Neither should the weak observation cells. */
  for (int i = 0; i < 5; i++) assert(!*observed[i]);
  gc_report();
  puts("bdwgc contract ok");
  return 0;
}
