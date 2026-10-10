#include <stdio.h>
void *pmake(long) __asm__("f.make"); long ptotal(void *) __asm__("f.total");
void c_entry(void) { void *l = pmake(20000); printf("C called JIT'd Pystachy: total %ld\n", ptotal(l)); fflush(stdout); }
