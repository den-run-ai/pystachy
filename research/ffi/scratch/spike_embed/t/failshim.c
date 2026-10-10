#include <stdint.h>
typedef struct { int64_t len; char s[]; } Str;
extern Str *pys_str(const char *p, int64_t n);
extern _Noreturn void pys_raise(Str *kind, Str *msg);
void py_fail_void(int64_t x) { pys_raise(pys_str("ValueError", 10), pys_str("from C (void)", 13)); }
int64_t py_fail_int(int64_t x) { pys_raise(pys_str("ValueError", 10), pys_str("from C (int)", 12)); }
