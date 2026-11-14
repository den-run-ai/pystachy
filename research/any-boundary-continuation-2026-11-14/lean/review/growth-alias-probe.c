#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef int64_t I;
#ifdef OVERLAP
typedef struct { I len, cap; union { I *a; I *ids; }; } List;
#else
typedef struct { I len, cap; I *a, *ids; } List;
#endif
#define INLINE_CAP 4
static I empty_inline[1];
static I *inline_items(List *l) { return (I *)(l + 1); }
static int atomic_items(const I *a) { (void)a; return 1; }
static I *item_array(I n, int atomic) { (void)atomic; return calloc(n, sizeof(I)); }
static void *pys_alloc(size_t size) { return calloc(1, size); }
static int opt_in(void) { return 1; }
static void oom(void) { abort(); }
static void reserve(List *l, I n) {
  if (n <= l->cap) return;
  I c = l->cap * 2 > n ? l->cap * 2 : n, *a;
  if (c < INLINE_CAP) c = INLINE_CAP;
  if (l->a == empty_inline && c == INLINE_CAP) a = inline_items(l);   /* (emptied, and its items fit inline again) */
  else {
    a = item_array(c, atomic_items(l->a));
    memcpy(a, l->a, l->len * 8);
    if (l->a == inline_items(l)) memset(l->a, 0, INLINE_CAP * sizeof(I));   /* (moved: the header keeps none of them) */
  }
  l->a = a;
  if (l->ids && opt_in()) {
    if (c > INT64_MAX / (I)sizeof(I) - 1) oom();
    I *ids = pys_alloc((c + 1) * sizeof(I));
    memcpy(ids, l->ids, (l->len + 1) * sizeof(I)); l->ids = ids;
  }
  l->cap = c;
}
int main(void) {
    List list = {0};
    I first_box = 17, last_box = 23;
    list.len = 2; list.cap = 4;
    list.a = calloc(5, sizeof(I));
#ifndef OVERLAP
    list.ids = calloc(5, sizeof(I));
#endif
    list.ids[0] = 1;
    list.ids[1] = (I)&first_box;
    list.ids[2] = (I)&last_box;
    reserve(&list, 8);
    printf("first identity preserved: %d; last identity preserved: %d\n",
           list.ids[1] == (I)&first_box, list.ids[2] == (I)&last_box);
    return 0;
}
