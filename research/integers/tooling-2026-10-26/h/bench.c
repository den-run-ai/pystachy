/* Times old_* and new_* mpz text conversion with a bump arena reset every iteration. */
#include "common.h"
#include <time.h>
#include "api.h"
DECL(old_)
DECL(new_)
static char *arena, *top, *keep;
void *pys_alloc_atomic(I n) { void *p = top; top += (n + 15) & ~(I)15; return memset(p, 0, n); }
_Noreturn void pys_fail(const char *m) { fprintf(stderr, "%s\n", m); exit(3); }
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
int main(int argc, char **argv) {
  const char *op = argv[1]; I digits = atoll(argv[2]), reps = atoll(argv[3]), base = argc > 4 ? atoll(argv[4]) : 10;
  arena = malloc((size_t)1 << 28); top = arena;
  Str *s = pys_alloc_atomic(sizeof(Str) + digits + 1); s->len = digits;
  for (I i = 0; i < digits; i++) s->s[i] = "1234567890abcdefghijklmnopqrstuvwxyz"[base > 10 ? (i % 10 + i / 10) % base : (i % 10 + i / 10) % (base - 1)];
  void *a = new_from_str(s, base);
  keep = top; I check = 0; double best[2] = {1e9, 1e9};
  for (int round = 0; round < 7; round++)
    for (int v = 0; v < 2; v++) {
      double t0 = now();
      for (I r = 0; r < reps; r++) {
        top = keep;
        if (!strcmp(op, "parse")) check += *(I *)(v ? new_from_str(s, base) : old_from_str(s, base));
        else check += (v ? new_str(a) : old_str(a))->len;
      }
      double t = (now() - t0) / reps * 1e6; if (t < best[v]) best[v] = t;
    }
  printf("%-6s %6lld digits base %2lld: old %9.3f us  new %9.3f us  (%.2fx)  [%lld]\n", op, (long long)digits,
         (long long)base, best[0], best[1], best[0] / best[1], (long long)(check & 1));
  return 0;
}
