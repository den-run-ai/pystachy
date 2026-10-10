#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
void plib_init(char *); void *plib_make(long); long plib_total(void *); void pys_finish(void);
static long expect(long n) { long t = 0; char b[32]; for (long i = 0; i < n; i++) t += 3 * snprintf(b, 32, "%ld", i); return t; }
static char *initfa;
__attribute__((noinline)) static int deep(int d) { volatile char buf[4096]; buf[0] = (char)d; if (d) return deep(d - 1) + buf[0]; initfa = __builtin_frame_address(0); plib_init(initfa); return 0; }
int main(int argc, char **argv) {
  int mode = atoi(argv[1]);
  if (mode == 1) deep(50); else { initfa = __builtin_frame_address(0); plib_init(initfa); }
  printf("init frame %p, main frame %p (init is %s main)\n", (void *)initfa, __builtin_frame_address(0), initfa < (char *)__builtin_frame_address(0) ? "deeper than" : "at/above");
  void *l = plib_make(20000);
  printf("total %ld expect %ld\n", plib_total(l), expect(20000));
  pys_finish();
  return 0;
}
