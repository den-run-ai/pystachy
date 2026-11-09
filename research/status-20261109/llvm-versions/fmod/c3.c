#include <math.h>
#include <stdio.h>
#include <stdlib.h>
__attribute__((noreturn, noinline)) static void fail(const char *m) { fputs(m, stderr); exit(1); }
static double m_fmod(double x, double y) {
  if ((isinf(x) || y == 0) && !isnan(x) && !isnan(y)) fail("ValueError: math domain error\n");
  return fmod(x, y);
}
__attribute__((noinline)) int probe(double x) { return isnan(m_fmod(x, 1.0)); }
int main(int argc, char **argv) {
  double x = strtod(argc > 1 ? argv[1] : "nan", 0);
  printf("isnan(fmod(%g, 1.0)) = %d (want %d)\n", x, probe(x), isnan(x) ? 1 : 0);
  return 0;
}
