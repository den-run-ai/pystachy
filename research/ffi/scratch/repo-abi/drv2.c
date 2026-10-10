#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
void plib_init(char *); void *plib_make(long); long plib_total(void *); void pys_finish(void);
static long expect(long n) { long t = 0; char b[32]; for (long i = 0; i < n; i++) t += 3 * snprintf(b, 32, "%ld", i); return t; }
__attribute__((noinline)) static void deep(int d) { volatile char buf[4096]; buf[0] = 0; if (d) { deep(d - 1); return; } plib_init(__builtin_frame_address(0)); }
static uintptr_t *hidden;
__attribute__((noinline)) static void stash(void) { hidden = malloc(8); *hidden = ~(uintptr_t)plib_make(20000); }  /* only a disguised copy survives */
__attribute__((noinline)) static void churn(void) { for (int k = 0; k < 3; k++) plib_make(20000); }
__attribute__((noinline)) static void clobber(void) { volatile char z[65536]; for (int i = 0; i < 65536; i++) z[i] = 0; }
int main(int argc, char **argv) {
  int mode = atoi(argv[1]);
  if (mode == 1) deep(50); else plib_init(__builtin_frame_address(0));
  if (mode == 2) {
    stash(); clobber(); churn();
    void *l = (void *)~*hidden; uintptr_t *w = l;
    printf("foreign-only list: len word now %ld (was 20000); total %ld expect %ld\n", (long)w[0], plib_total(l), expect(20000));
  } else {
    void *l = plib_make(20000);
    printf("total %ld expect %ld\n", plib_total(l), expect(20000));
  }
  pys_finish();
  return 0;
}
