/* LD_PRELOAD counter of libm calls made through the PLT: pow, floor, trunc. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
static unsigned long n_pow, n_floor, n_trunc;
static double (*real_pow)(double, double);
static double (*real_floor)(double);
static double (*real_trunc)(double);
double pow(double a, double b) { if (!real_pow) real_pow = (double (*)(double, double))dlsym(RTLD_NEXT, "pow"); n_pow++; return real_pow(a, b); }
double floor(double x) { if (!real_floor) real_floor = (double (*)(double))dlsym(RTLD_NEXT, "floor"); n_floor++; return real_floor(x); }
double trunc(double x) { if (!real_trunc) real_trunc = (double (*)(double))dlsym(RTLD_NEXT, "trunc"); n_trunc++; return real_trunc(x); }
__attribute__((destructor)) static void report(void) { fprintf(stderr, "libm calls: pow %lu floor %lu trunc %lu\n", n_pow, n_floor, n_trunc); }
