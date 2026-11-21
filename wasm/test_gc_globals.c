/* This test reactor runs a single collection after the guest has returned.
   Only references in the guest's relocated global slots can retain its lists. */
#define pys_finish finish_without_probe
#include "../runtime.c"
#undef pys_finish

void pys_finish(void) {
  if (!gc_off || gc_nroots != 2) {
    fputs("expected disabled automatic collection and two program roots\n", stderr);
    exit(1);
  }
  collect();
  I live_headers = 0;
  for (Seg *s = chunks; s; s = s->next)
    if (s->k == 2 * cls(sizeof(List) - 1)) live_headers += s->nlive;
  if (live_headers != 2) {
    fprintf(stderr, "expected two live list headers, found %lld\n", (long long)live_headers);
    exit(1);
  }
  I values = 0;
  for (I i = 0; i < gc_nroots; i++) {
    List *list = *(List **)gc_roots[i];
    if (list && list->len == 1) {
      if (list->a[0] == 23) values |= 1;
      if (list->a[0] == 29) values |= 2;
    }
  }
  if (values != 3) {
    fputs("retained list contents differ\n", stderr);
    exit(1);
  }
  finish_without_probe();
}
