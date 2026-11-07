/* Optional experiment, linked separately so the compiler driver's LLVM target
   attribute normalization cannot remove StringZilla's per-function ISA guards.
   Upstream StringZilla is supplied by the runner at a pinned commit; no source is
   vendored here. See bench/text_kernels/README.md for provenance and licensing. */
#include <stdint.h>
#if defined(__x86_64__) && defined(__clang__)
#define SZ_USE_HASWELL 1
#endif
#include <stringzilla/find.h>

static int adapter_haswell;
#if defined(__x86_64__) && defined(__clang__)
#include <cpuid.h>
__attribute__((constructor)) static void select_backend(void) {
  unsigned a, b, c, d;
  __builtin_cpu_init();
  /* clang 18's feature builtin has no lzcnt spelling. Extended CPUID bit 5
     is its architectural feature bit; test it separately before Haswell code. */
  adapter_haswell = __builtin_cpu_supports("avx2") && __builtin_cpu_supports("bmi") &&
                    __builtin_cpu_supports("bmi2") &&
                    __get_cpuid(0x80000001, &a, &b, &c, &d) && (c & (1u << 5));
}
#endif
const char *pystachy_stringzilla_backend(void) {
  return adapter_haswell ? "haswell-avx2" : "serial";
}
int64_t pystachy_stringzilla_json_scan(const char *text, int64_t length) {
  sz_byteset_t stop;
  sz_byteset_init(&stop);
  for (unsigned c = 0; c < 32; c++) sz_byteset_add_u8(&stop, (sz_u8_t)c);
  sz_byteset_add_u8(&stop, 34);
  sz_byteset_add_u8(&stop, 92);
  const char *found;
#if defined(__x86_64__) && defined(__clang__)
  if (adapter_haswell) found = sz_find_byteset_haswell(text, (sz_size_t)length, &stop);
  else
#endif
    found = sz_find_byteset_serial(text, (sz_size_t)length, &stop);
  return found ? found - text : length;
}
