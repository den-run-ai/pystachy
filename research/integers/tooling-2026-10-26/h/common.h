/* Stubs standing in for runtime.c's helpers so mpz.c compiles on its own. */
#include <setjmp.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int64_t I;
typedef struct { I len; uint64_t dict_hash; I chars1; char s[]; } Str;
void *pys_alloc_atomic(I n);
_Noreturn void pys_fail(const char *m);
static _Noreturn void failf(const char *f, ...) {
  char b[512]; va_list ap; va_start(ap, f); vsnprintf(b, sizeof b, f, ap); va_end(ap); pys_fail(b);
}
static _Noreturn void badlit(const char *what, I base, Str *s) {
  char b[512]; snprintf(b, sizeof b, "%s with base %lld: '%.40s'", what, (long long)base, s->s); pys_fail(b);
}
static Str *asciinum(Str *s) { return s; }
static int digitv(char c) { return c >= '0' && c <= '9' ? c - '0' : (c | 32) >= 'a' && (c | 32) <= 'z' ? (c | 32) - 'a' + 10 : 99; }
static int aws(unsigned char c) { return c == ' ' || (c >= 9 && c <= 13); }
static Str *cstr(const char *p) {
  I n = strlen(p); Str *s = pys_alloc_atomic(sizeof(Str) + n + 1); s->len = n; s->chars1 = n + 1; memcpy(s->s, p, n); return s;
}
