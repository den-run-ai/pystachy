/* Exercise the shared collector on wasm32 with one explicitly registered root.
   Build the graph in a separate activation so the collector cannot find leaves
   through the construction routine's locals. Guest collection stays disabled. */
#include "../runtime.c"

static W *parent;

enum { LEAF_BYTES = 57, ATOMIC_CHILD_BYTES = 73, LIVE_LEAVES = 6 };

__attribute__((noinline)) static void build_graph(void) {
  W *array = pys_alloc(3 * PAGE + sizeof(W));
  W *small = pys_alloc(16);
  W *atomic = pys_alloc_atomic(15);
  small[16 / sizeof(W) - 1] = (W)pys_alloc_atomic(LEAF_BYTES);
  atomic[0] = (W)pys_alloc_atomic(ATOMIC_CHILD_BYTES);   /* unreachable through an atomic object */
  array[0] = (W)small;
  array[1] = (W)atomic;
  for (int page = 1; page <= 2; page++) {
    array[page * PAGE / sizeof(W) - 1] = (W)pys_alloc_atomic(LEAF_BYTES);
    array[page * PAGE / sizeof(W)] = (W)pys_alloc_atomic(LEAF_BYTES);
  }
  array[3 * PAGE / sizeof(W)] = (W)pys_alloc_atomic(LEAF_BYTES);   /* last complete pointer */
  parent = array;
}

int main(void) {
  I *roots[] = {(I *)&parent};
  gc_init(__builtin_frame_address(0), roots, 1);
  if (!gc_off) return 1;
  build_graph();
  collect();   /* force this one controlled collection without enabling automatic collections */
  I leaves = 0;
  for (Seg *s = chunks; s; s = s->next)
    if (s->k == 2 * cls(LEAF_BYTES) + 1) leaves += s->nlive;
    else if (s->k == 2 * cls(ATOMIC_CHILD_BYTES) + 1 && s->nlive) {
      fputs("marked a child through an atomic object\n", stderr);
      return 1;
    }
  if (leaves != LIVE_LEAVES) {
    fprintf(stderr, "expected %d live leaves, found %lld\n", LIVE_LEAVES, (long long)leaves);
    return 1;
  }
  return 0;
}
