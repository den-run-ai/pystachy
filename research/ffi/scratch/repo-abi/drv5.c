#include <stdio.h>
#include <stdlib.h>
void plib_init(char *); long plib_try_through_c(long); void pys_finish(void);
static int depth;
long c_apply(long (*f)(long), long n) { depth++; long r = f(n); depth--; printf("c_apply: callee returned normally\n"); return r; }
int main(void) {
  plib_init(__builtin_frame_address(0));
  printf("ok path: %ld\n", plib_try_through_c(1));
  printf("raise path: %ld (C frame's depth-- skipped: depth=%d)\n", plib_try_through_c(2), depth);
  pys_finish();
  return 0;
}
