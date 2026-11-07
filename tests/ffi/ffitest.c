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

/* tests/ffi/ext/recdeepclient.py's native stack, through ctypes: n frames of 4 KiB below its caller, then
   cb(n, the address of the deepest frame's buffer); not a tail call (each frame's buffer is read after it) */
long ffi_deep(long n, long (*cb)(long, long)) {
  volatile char buf[4096];
  buf[0] = (char)n;
  long r = n > 0 ? ffi_deep(n - 1, cb) : cb(n, (long)(intptr_t)buf);
  return r + buf[0] - (char)n;
}

/* Binary buffers and pointer cells used by the FFI and ctypes compatibility probes. */
static unsigned char ffi_bytes_data[] = {0xff, 0x80, 0, 'A', 0};
unsigned ffi_bytes_sum(const unsigned char *s, size_t n) {
  unsigned sum = 0;
  for (size_t i = 0; i < n; i++) sum += s[i];
  return sum;
}
/* ctypes' prototype has signed32 lengths, so its probe declares this exact ABI. */
unsigned ffi_ctypes_bytes_sum(const unsigned char *s, int n) {
  return ffi_bytes_sum(s, (size_t)n);
}
const char *ffi_bytes_result(int present) { return present ? (const char *)ffi_bytes_data : NULL; }
int ffi_bytes_is_null(const char *s) { return s == NULL; }
void ffi_bytes_change(int x) { ffi_bytes_data[0] = (unsigned char)x; }
void *ffi_pointer_echo(void *p) { return p; }
void ffi_pointer_set(void **p) { *p = ffi_bytes_data; }
int ffi_pointer_alias(void **a, void **b) { return a == b; }
int ffi_echo_int(int x) { return x; }
unsigned ffi_echo_uint(unsigned x) { return x; }
int64_t ffi_echo_int64(int64_t x) { return x; }
float ffi_echo_float(float x) { return x; }
double ffi_echo_double(double x) { return x; }
