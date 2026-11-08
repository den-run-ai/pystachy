/* Float parsing uses the real runtime: deterministic allocation counts and
   exact-terminator guard pages. Link runtime.py's IR; run with make floatprobe. */
#define PYSTACHY_PROFILE_DATA
#include "../runtime.c"

I pys_obj_eq(I c, I a, I b) { (void)c; return a == b; }
I pys_obj_cmp(I c, I op, I a, I b) { (void)c; (void)op; return a < b ? -1 : a > b; }
Str *pys_obj_repr(I c, I a, I b) { (void)c; (void)a; (void)b; return cstr("<object>"); }
static Str *current;
static I *roots[] = {(I *)&current};

static void sample(const char *source, double expected, uint64_t allocations) {
  current = cstr(source);
  uint64_t before = atomic_load_explicit(&profile_alloc_calls, memory_order_relaxed);
  double value = pys_float_str(current);
  uint64_t after = atomic_load_explicit(&profile_alloc_calls, memory_order_relaxed);
  if (value != expected || (value == 0 && signbit(value) != signbit(expected)) || after - before != allocations) {
    fprintf(stderr, "floatprobe: incorrect value or allocation count for %s\n", source);
    abort();
  }
}

int main(void) {
  gc_init(__builtin_frame_address(0), roots, 1);
  pys_c_numeric();
  sample("12.5", 12.5, 0);
  sample("  -0", -0.0, 0);
  sample("12.5 \t", 12.5, 1);
  sample("1_2.5", 12.5, 1);
  sample("+InF", INFINITY, 0);
  sample("1e-9999", 0.0, 0);
  long page = sysconf(_SC_PAGESIZE);
  if (page < 1024) abort();
  char *mapping = mmap(NULL, (size_t)page * 2, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (mapping == MAP_FAILED || mprotect(mapping, (size_t)page, PROT_READ | PROT_WRITE)) abort();
  for (I length = 7; length < 512; length += 8) {
    /* Keep the header naturally aligned and its NUL in the last readable byte. */
    Str *s = (Str *)(mapping + page - sizeof(Str) - length - 1);
    s->len = length; s->dict_hash = 0; s->chars1 = length + 1;
    memset(s->s, '0', (size_t)length); s->s[length - 1] = '1'; s->s[length] = 0;
    if (pys_float_str(s) != 1.0) abort();
  }
  if (munmap(mapping, (size_t)page * 2)) abort();
  puts("floatprobe: 6 allocation checks and 64 exact-terminator guard-page spans passed");
  return 0;
}
