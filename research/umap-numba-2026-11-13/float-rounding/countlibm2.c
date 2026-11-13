/* LD_PRELOAD counter of libm calls made through the PLT, by function. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#define F1(name) static unsigned long n_##name; static double (*r_##name)(double); \
  double name(double x) { if (!r_##name) r_##name = (double (*)(double))dlsym(RTLD_NEXT, #name); n_##name++; return r_##name(x); }
#define F2(name) static unsigned long n_##name; static double (*r_##name)(double, double); \
  double name(double x, double y) { if (!r_##name) r_##name = (double (*)(double, double))dlsym(RTLD_NEXT, #name); n_##name++; return r_##name(x, y); }
F2(pow) F1(floor) F1(ceil) F1(trunc) F1(round) F1(nearbyint) F1(rint) F2(fmod) F1(exp) F1(log) F1(log2) F1(log10)
F1(sin) F1(cos) F1(tan) F1(atan) F2(atan2) F2(hypot) F1(sqrt) F1(exp2) F1(expm1) F1(log1p) F1(tanh) F1(cbrt) F1(asin) F1(acos)
static unsigned long n_modf; static double (*r_modf)(double, double *);
double modf(double x, double *i) { if (!r_modf) r_modf = (double (*)(double, double *))dlsym(RTLD_NEXT, "modf"); n_modf++; return r_modf(x, i); }
#define P(name) if (n_##name) fprintf(stderr, " %s=%lu", #name, n_##name);
__attribute__((destructor)) static void report(void) {
  fprintf(stderr, "libm:");
  P(pow) P(floor) P(ceil) P(trunc) P(round) P(nearbyint) P(rint) P(fmod) P(modf) P(exp) P(log) P(log2) P(log10)
  P(sin) P(cos) P(tan) P(atan) P(atan2) P(hypot) P(sqrt) P(exp2) P(expm1) P(log1p) P(tanh) P(cbrt) P(asin) P(acos)
  fprintf(stderr, "\n");
}
