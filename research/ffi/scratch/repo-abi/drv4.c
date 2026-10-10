#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
void plib_init(char *); void *plib_make(long); long plib_total(void *); void pys_finish(void);
static uintptr_t *hidden;
__attribute__((noinline)) static void stash(void) { hidden = malloc(8); *hidden = ~(uintptr_t)plib_make(2000); }
__attribute__((noinline)) static void clobber(void) { volatile char z[1 << 20]; memset((char *)z, 0, sizeof z); }
__attribute__((noinline)) static void churn(void) { for (int k = 0; k < 3; k++) plib_make(777); }
int main(int argc, char **argv) {
  plib_init(__builtin_frame_address(0));
  stash(); clobber(); churn();
  uintptr_t *w = (uintptr_t *)~*hidden;
  printf("list held only by malloc'd memory: len word %ld cap %ld items %p (was len 2000)\n", (long)w[0], (long)w[1], (void *)w[2]);
  fflush(stdout);
  printf("total %ld\n", plib_total(w));
  pys_finish();
  return 0;
}
