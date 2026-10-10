#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void plib_init(char *); void *plib_make(long); long plib_total(void *); long plib_lookup(long); long plib_boom(long);
static long expect(long n) { long t = 0; char b[32]; for (long i = 0; i < n; i++) t += 3 * snprintf(b, 32, "%ld", i); return t; }
__attribute__((noinline)) static void deep(int d) { volatile char buf[4096]; buf[0] = 0; if (d) { deep(d - 1); return; } plib_init(__builtin_frame_address(0)); }
int main(int argc, char **argv) {
  int mode = atoi(argv[1]); long n = 20000;
  if (mode == 0 || mode == 2 || mode == 3) plib_init(__builtin_frame_address(0));   /* shallow init */
  else deep(50);                                                        /* init from a deep frame */
  if (mode == 2) {                     /* keep a Pystachy list only in malloc'd memory */
    void **box = malloc(sizeof *box); *box = plib_make(n);
    for (int k = 0; k < 5; k++) plib_make(n);   /* allocate: collections run */
    printf("foreign-held total %ld expect %ld\n", plib_total(*box), expect(n));
    return 0;
  }
  if (mode == 3) { printf("lookup(1)=%ld lookup(2)=%ld\n", plib_lookup(1), plib_lookup(2)); printf("boom(2) -> "); fflush(stdout); printf("%ld\n", plib_boom(2)); printf("after boom (not reached?)\n"); return 0; }
  void *l = plib_make(n);
  printf("total %ld expect %ld\n", plib_total(l), expect(n));
  return 0;
}
