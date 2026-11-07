/* Parser copy/temporary-allocation accounting plus terminator guard pages.
   Linked with the actual runtime.py IR by bench/text_kernels/run.py. */
static long long copied, raw_calls, raw_bytes;
#define FLOAT_PARSE_COPY(n) (copied += (n))
#define GC_RAW_REQUEST(n) (raw_calls++, raw_bytes += (n))
#include "../../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }
static Str *current;
static I *roots[] = {(I *)&current};
static void sample(const char *source, double expected, long long span_copies) {
  current = cstr(source);
  copied = raw_calls = raw_bytes = 0;
  double value = pys_float_str(current);
  if (value != expected || (value == 0 && signbit(value) != signbit(expected))) abort();
#ifdef PYSTACHY_FLOAT_SPAN
  if (copied != span_copies || raw_calls != (span_copies > 0)) abort();
#else
  (void)span_copies;
  if (copied == 0 || raw_calls <= 0 || raw_bytes <= 0) abort();
#endif
  printf("floatprobe: %s, parser copy bytes=%lld, raw allocation requests=%lld, requested bytes=%lld\n",
         source, copied, raw_calls, raw_bytes);
}
int main(void) {
  gc_init(__builtin_frame_address(0), roots, 1);
  pys_c_numeric();
  sample("12.5", 12.5, 0);
  sample("  -0", -0.0, 0);
  sample("12.5 \t", 12.5, 5);
  sample("1_2.5", 12.5, 5);
  sample("+InF", INFINITY, 0);
  sample("1e-9999", 0.0, 0);
  long page = sysconf(_SC_PAGESIZE);
  char *mapping = mmap(NULL, (size_t)page * 2, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (mapping == MAP_FAILED || mprotect(mapping, (size_t)page, PROT_READ | PROT_WRITE)) abort();
  for (I length = 7; length < 512; length += 8) {
    /* Keep the Str header naturally aligned, with NUL in the last readable byte. */
    Str *s = (Str *)(mapping + page - sizeof(Str) - length - 1);
    s->len = length; s->dict_hash = 0; s->chars1 = length + 1;
    memset(s->s, '0', (size_t)length); s->s[length - 1] = '1'; s->s[length] = 0;
    if (pys_float_str(s) != 1.0) abort();
  }
  if (munmap(mapping, (size_t)page * 2)) abort();
  puts("floatprobe: 64 exact-terminator guard-page spans passed");
  return 0;
}
