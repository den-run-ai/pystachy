double fmod(double, double);
__attribute__((noreturn)) void fail(const char *);
static double m_fmod(double x, double y) {
  if ((__builtin_isinf(x) || y == 0) && !__builtin_isnan(x) && !__builtin_isnan(y)) fail("domain");
  return fmod(x, y);
}
int probe(double x) { return __builtin_isnan(m_fmod(x, 1.0)); }
