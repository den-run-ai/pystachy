/* tests/ffi/c_lib.py's library (tests/ffi/run.sh builds it as libpystachy-ffitest.so): functions named
   as functions of libraries that lli's process has loaded already (libz's, libzstd's), which an
   @extern of this library must still find here, as ctypes does */
const char *zlibVersion(void) { return "ffitest"; }
unsigned ZSTD_versionNumber(void) { return 42; }

/* tests/ffi/c_lists.py's kernels: arrays a list[float] or list[c_int64] lends for the call, which
   they read and write in place; reverse() reads x after writing y, so a list passed as both shows
   whether x and y are one array (they must be, natively and in tools/rt_cpython's twin) */
#include <stddef.h>
#include <stdint.h>
double ffi_sum(const double *x, size_t n) { double s = 0.0; for (size_t i = 0; i < n; i++) s += x[i]; return s; }
void ffi_axpy(size_t n, double a, const double *x, double *y) { for (size_t i = 0; i < n; i++) y[i] += a * x[i]; }
void ffi_scale(double *x, size_t n, double k) { for (size_t i = 0; i < n; i++) x[i] *= k; }
void ffi_reverse(const double *x, double *y, size_t n) { for (size_t i = 0; i < n; i++) y[i] = x[n - 1 - i]; }
int64_t ffi_isum(const int64_t *x, size_t n) { int64_t s = 0; for (size_t i = 0; i < n; i++) s += x[i]; return s; }
void ffi_iota(int64_t *x, size_t n, int64_t start) { for (size_t i = 0; i < n; i++) x[i] = start + (int64_t)i; }

/* tests/ffi/c_float.py's functions of C floats (ffi.c_float) */
double ffi_widen(float x) { return x; }
float ffi_narrow(double x) { return (float)x; }
float ffi_fmul(float a, float b) { return a * b; }
