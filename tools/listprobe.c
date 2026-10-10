/* Empty reachable lists must not retain their historical capacity. These are deterministic
   capacity and live-byte checks, not RSS/timing thresholds. Like dictprobe, this includes the
   real runtime and links runtime.py's IR. usage: make listprobe */
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }

static List *buffers;
static I *roots[] = {(I *)&buffers};
static _Noreturn void bad(const char *what) { fprintf(stderr, "listprobe: %s\n", what); exit(1); }
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
  List l = {0, 0, sorting};
  pys_list_clear(&l);
  if (l.a != sorting) bad("clear modifies untouched sort sentinel");
  pys_list_append(&l, 1);
  pys_list_clear(&l);
  if (l.a == sorting) bad("clear hides mutation during sort");
}
int main(void) {
  gc_init(__builtin_frame_address(0), roots, 1);
  clear_many();
  scrub_collect();
  scrub_collect();
  if (gc_live >= 1048576) bad("cleared list storage survives collection");
  for (I i = 0; i < buffers->len; i++) check_empty((List *)buffers->a[i]);
  operations();
  puts("listprobe: empty-list capacity, collection and reuse passed");
  return 0;
}
