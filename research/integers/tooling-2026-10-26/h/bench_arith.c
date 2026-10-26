/* Times old_* (main) and new_* (edited) mpz arithmetic, bump arena reset every iteration. */
#include "common.h"
#include <time.h>
#include "api.h"
DECL(old_)
DECL(new_)
static char *arena, *top, *keep;
void *pys_alloc_atomic(I n) { void *p = top; top += (n + 15) & ~(I)15; return memset(p, 0, n); }
_Noreturn void pys_fail(const char *m) { fprintf(stderr, "%s\n", m); exit(3); }
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
static Str *text(I digits, int salt) {
  Str *s = pys_alloc_atomic(sizeof(Str) + digits + 1); s->len = digits;
  for (I i = 0; i < digits; i++) s->s[i] = '0' + (i * 7 + salt + i / 13) % 10;
  s->s[0] = '9'; return s;
}
int main(int argc, char **argv) {
  const char *op = argv[1]; I digits = atoll(argv[2]), reps = atoll(argv[3]);
  arena = malloc((size_t)1 << 30); top = arena;
  void *a = new_from_str(text(digits, 1), 10), *b = new_from_str(text(digits, 5), 10);
  void *small = new_from_str(text(digits / 3 + 1, 3), 10);
  keep = top; I check = 0; double best[2] = {1e9, 1e9};
  for (int round = 0; round < 7; round++)
    for (int v = 0; v < 2; v++) {
      double t0 = now();
      for (I r = 0; r < reps; r++) {
        top = keep; void *x;
        if (!strcmp(op, "add")) x = v ? new_binop(a, b, 0) : old_binop(a, b, 0);
        else if (!strcmp(op, "sub")) x = v ? new_binop(a, b, 1) : old_binop(a, b, 1);
        else if (!strcmp(op, "mul")) x = v ? new_binop(a, b, 2) : old_binop(a, b, 2);
        else if (!strcmp(op, "sqr")) x = v ? new_binop(a, a, 2) : old_binop(a, a, 2);
        else if (!strcmp(op, "lop")) x = v ? new_binop(a, small, 2) : old_binop(a, small, 2);
        else x = v ? new_binop(a, small, 3) : old_binop(a, small, 3);
        check += *(I *)x;
      }
      double t = (now() - t0) / reps * 1e6; if (t < best[v]) best[v] = t;
    }
  printf("%-4s %6lld digits: old %10.3f us  new %10.3f us  (%.2fx)  [%lld]\n", op, (long long)digits,
         best[0], best[1], best[0] / best[1], (long long)(check & 1));
  return 0;
}
