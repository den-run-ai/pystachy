/* Pystachy runtime: strings, lists, dicts, printing and I/O.
   Compiled to LLVM bitcode and linked into every program, so LLVM inlines these
   helpers across the program boundary (whole-program optimization).
   Value model: every container slot is 8 bytes (int, float bits, bool, or pointer). */
#define _GNU_SOURCE
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef int64_t I;
typedef struct { I len; char s[]; } Str;              /* immutable, NUL-terminated */
typedef struct { I len, cap; I *a; } List;
typedef struct { I len, kind, cap; I *keys, *vals, *idx; } Dict; /* insertion-ordered; kind 1 = str keys */
typedef struct { char *p; I n, cap; } Buf;
#define NONE INT64_MIN                                 /* omitted slice bound */

/* ---------- memory: bump allocator, never frees (batch-program model) ---------- */
static char *hp, *he;
void *pys_alloc(I n) {
  n = n ? (n + 7) & ~7 : 8;
  if (n > he - hp) {
    I c = n > (8 << 20) ? n : (8 << 20);
    if (!(hp = calloc(1, c))) { fputs("MemoryError\n", stderr); exit(1); }
    he = hp + c;
  }
  void *p = hp; hp += n; return p;
}

_Noreturn void pys_fail(const char *m) { fflush(stdout); fprintf(stderr, "%s\n", m); exit(1); }
_Noreturn void pys_raise(Str *kind, Str *msg) {
  fflush(stdout);
  if (msg->len) fprintf(stderr, "%s: %s\n", kind->s, msg->s); else fprintf(stderr, "%s\n", kind->s);
  exit(1);
}

static void put(Buf *b, const char *s, I n) {
  if (b->n + n > b->cap) {
    I c = b->cap * 2 + n + 64; char *p = pys_alloc(c);
    if (b->n) memcpy(p, b->p, b->n);
    b->p = p; b->cap = c;
  }
  memcpy(b->p + b->n, s, n); b->n += n;
}

/* ---------- strings ---------- */
Str *pys_str(const char *p, I n) { Str *s = pys_alloc(sizeof(Str) + n + 1); s->len = n; if (n) memcpy(s->s, p, n); return s; }
static Str *cstr(const char *p) { return pys_str(p, strlen(p)); }
static Str *done(Buf *b) { return pys_str(b->p, b->n); }
static Str *ch1[256];
Str *pys_chr(I c) {
  if (c < 0 || c > 255) pys_fail("ValueError: chr() arg not in range(256)");
  if (!ch1[c]) { char b = (char)c; ch1[c] = pys_str(&b, 1); }
  return ch1[c];
}
I pys_ord(Str *s) { if (s->len != 1) pys_fail("TypeError: ord() expected a character"); return (unsigned char)s->s[0]; }
static I idx(I i, I n, const char *m) { if (i < 0) i += n; if (i < 0 || i >= n) pys_fail(m); return i; }
static void span(I *lo, I *hi, I n) {
  if (*lo == NONE) *lo = 0; else if (*lo < 0 && (*lo += n) < 0) *lo = 0; else if (*lo > n) *lo = n;
  if (*hi == NONE) *hi = n; else if (*hi < 0 && (*hi += n) < 0) *hi = 0; else if (*hi > n) *hi = n;
  if (*hi < *lo) *hi = *lo;
}
Str *pys_str_get(Str *s, I i) { return pys_chr((unsigned char)s->s[idx(i, s->len, "IndexError: string index out of range")]); }
Str *pys_str_slice(Str *s, I lo, I hi) { span(&lo, &hi, s->len); return pys_str(s->s + lo, hi - lo); }
Str *pys_str_add(Str *a, Str *b) {
  Str *s = pys_alloc(sizeof(Str) + a->len + b->len + 1);
  s->len = a->len + b->len; memcpy(s->s, a->s, a->len); memcpy(s->s + a->len, b->s, b->len); return s;
}
Str *pys_str_mul(Str *a, I n) {
  if (n < 0) n = 0;
  if (n && a->len > (INT64_MAX - 64) / n) pys_fail("OverflowError: repeated string is too long");
  Str *s = pys_alloc(sizeof(Str) + a->len * n + 1); s->len = a->len * n;
  for (I i = 0; i < n; i++) memcpy(s->s + i * a->len, a->s, a->len);
  return s;
}
I pys_str_eq(Str *a, Str *b) { return a == b || (a->len == b->len && !memcmp(a->s, b->s, a->len)); }
I pys_str_cmp(Str *a, Str *b) {
  int c = memcmp(a->s, b->s, a->len < b->len ? a->len : b->len);
  return c ? c : (a->len > b->len) - (a->len < b->len);
}
static I find(Str *h, Str *n, I i) {
  char *p = i <= h->len ? memmem(h->s + i, h->len - i, n->s, n->len) : 0;
  return p ? p - h->s : -1;
}
static I start(I s, I n) { if (s < 0 && (s += n) < 0) s = 0; return s; }
I pys_str_find(Str *h, Str *n, I s) { return find(h, n, start(s, h->len)); }
I pys_str_rfind(Str *h, Str *n) {
  for (I i = h->len - n->len; i >= 0; i--) if (!memcmp(h->s + i, n->s, n->len)) return i;
  return -1;
}
I pys_str_index(Str *h, Str *n) { I i = find(h, n, 0); if (i < 0) pys_fail("ValueError: substring not found"); return i; }
I pys_str_count(Str *h, Str *n) {
  I c = 0;
  if (!n->len) return h->len + 1;
  for (I i = 0; (i = find(h, n, i)) >= 0; i += n->len) c++;
  return c;
}
I pys_str_contains(Str *h, Str *n) { return find(h, n, 0) >= 0; }
I pys_str_startswith(Str *s, Str *p, I i) { i = start(i, s->len); return i + p->len <= s->len && !memcmp(s->s + i, p->s, p->len); }
I pys_str_endswith(Str *s, Str *p) { return p->len <= s->len && !memcmp(s->s + s->len - p->len, p->s, p->len); }
Str *pys_str_replace(Str *s, Str *a, Str *b) {
  Buf o = {0}; I i = 0;
  if (!a->len) {
    for (; i < s->len; i++) { put(&o, b->s, b->len); put(&o, s->s + i, 1); }
    put(&o, b->s, b->len); return done(&o);
  }
  for (I j; (j = find(s, a, i)) >= 0; i = j + a->len) { put(&o, s->s + i, j - i); put(&o, b->s, b->len); }
  put(&o, s->s + i, s->len - i); return done(&o);
}
static int ws(unsigned char c) { return c == ' ' || (c >= 9 && c <= 13) || (c >= 28 && c <= 31); }
static int instr(unsigned char c, Str *cs) { return cs ? memchr(cs->s, c, cs->len) != 0 : ws(c); }
static Str *strip(Str *s, Str *cs, int m) {
  I i = 0, j = s->len;
  if (m & 1) while (i < j && instr(s->s[i], cs)) i++;
  if (m & 2) while (j > i && instr(s->s[j - 1], cs)) j--;
  return pys_str(s->s + i, j - i);
}
Str *pys_str_strip(Str *s, Str *cs) { return strip(s, cs, 3); }
Str *pys_str_lstrip(Str *s, Str *cs) { return strip(s, cs, 1); }
Str *pys_str_rstrip(Str *s, Str *cs) { return strip(s, cs, 2); }
static I all(Str *s, int k) {                  /* 0 digit, 1 alpha, 2 alnum, 3 space */
  if (!s->len) return 0;
  for (I i = 0; i < s->len; i++) {
    unsigned char c = s->s[i];
    int d = c >= '0' && c <= '9', a = (c | 32) >= 'a' && (c | 32) <= 'z';
    if (!(k == 0 ? d : k == 1 ? a : k == 2 ? d || a : ws(c))) return 0;
  }
  return 1;
}
static I cased(Str *s, int up) {               /* isupper / islower */
  int any = 0;
  for (I i = 0; i < s->len; i++) {
    char c = s->s[i];
    if (c >= 'a' && c <= 'z') { if (up) return 0; any = 1; }
    if (c >= 'A' && c <= 'Z') { if (!up) return 0; any = 1; }
  }
  return any;
}
I pys_str_isdigit(Str *s) { return all(s, 0); }
I pys_str_isalpha(Str *s) { return all(s, 1); }
I pys_str_isalnum(Str *s) { return all(s, 2); }
I pys_str_isspace(Str *s) { return all(s, 3); }
I pys_str_isupper(Str *s) { return cased(s, 1); }
I pys_str_islower(Str *s) { return cased(s, 0); }
static Str *mapc(Str *s, int up) {
  Str *r = pys_str(s->s, s->len);
  for (I i = 0; i < r->len; i++) {
    char c = r->s[i];
    if (up && c >= 'a' && c <= 'z') r->s[i] = c - 32;
    if (!up && c >= 'A' && c <= 'Z') r->s[i] = c + 32;
  }
  return r;
}
Str *pys_str_upper(Str *s) { return mapc(s, 1); }
Str *pys_str_lower(Str *s) { return mapc(s, 0); }
static Str *pad(Str *s, I w, int left) {
  if (s->len >= w) return s;
  Str *r = pys_alloc(sizeof(Str) + w + 1); r->len = w; memset(r->s, ' ', w);
  memcpy(r->s + (left ? 0 : w - s->len), s->s, s->len); return r;
}
Str *pys_str_ljust(Str *s, I w) { return pad(s, w, 1); }
Str *pys_str_rjust(Str *s, I w) { return pad(s, w, 0); }
Str *pys_str_int(I v) { char b[32]; return pys_str(b, snprintf(b, 32, "%lld", (long long)v)); }
Str *pys_str_float(double d) {               /* Python repr(): shortest round-trip digits */
  char b[40], dig[24], o[64], *w = o;
  if (isnan(d)) return cstr("nan");
  if (isinf(d)) return cstr(d > 0 ? "inf" : "-inf");
  if (d == 0) return cstr(signbit(d) ? "-0.0" : "0.0");
  int p = 1;
  for (; p < 17; p++) { snprintf(b, 40, "%.*e", p - 1, d); if (strtod(b, 0) == d) break; }
  if (p == 17) snprintf(b, 40, "%.16e", d);
  int nd = 0, neg = b[0] == '-';
  char *q = b + neg;
  for (; *q != 'e'; q++) if (*q != '.') dig[nd++] = *q;
  int e = atoi(q + 1) + 1;                      /* position of the decimal point */
  while (nd > 1 && dig[nd - 1] == '0') nd--;
  if (neg) *w++ = '-';
  if (e > -4 && e <= 16) {
    if (e <= 0) { *w++ = '0'; *w++ = '.'; for (int i = 0; i < -e; i++) *w++ = '0'; memcpy(w, dig, nd); w += nd; }
    else if (e >= nd) { memcpy(w, dig, nd); w += nd; for (int i = nd; i < e; i++) *w++ = '0'; *w++ = '.'; *w++ = '0'; }
    else { memcpy(w, dig, e); w += e; *w++ = '.'; memcpy(w, dig + e, nd - e); w += nd - e; }
  } else {
    *w++ = dig[0];
    if (nd > 1) { *w++ = '.'; memcpy(w, dig + 1, nd - 1); w += nd - 1; }
    w += sprintf(w, "e%c%02d", e - 1 < 0 ? '-' : '+', abs(e - 1));
  }
  return pys_str(o, w - o);
}
Str *pys_float_hex(double d) { char b[40]; return pys_str(b, snprintf(b, 40, "%.13a", d)); }
I pys_float_is_integer(double d) { return isfinite(d) && d == floor(d); }
static void badnum(const char *what, Str *s) {
  Buf b = {0}; put(&b, what, strlen(what)); put(&b, s->s, s->len); put(&b, "'", 2); pys_fail(b.p);
}
I pys_int_str(Str *s, I base) {
  char *e; errno = 0; I v = strtoll(s->s, &e, (int)base);
  while (*e && ws(*e)) e++;
  if (e == s->s || *e || !s->len) badnum("ValueError: invalid literal for int(): '", s);
  if (errno == ERANGE) badnum("OverflowError: int too large for 64 bits: '", s);
  return v;
}
double pys_float_str(Str *s) {
  char *e; double v = strtod(s->s, &e);
  while (*e && ws(*e)) e++;
  if (e == s->s || *e || !s->len) badnum("ValueError: could not convert string to float: '", s);
  return v;
}

/* ---------- arithmetic with Python semantics ----------
   ints are 64-bit: a result CPython would represent as a big int raises OverflowError */
#define ZDE "ZeroDivisionError: integer division or modulo by zero"
#define OVF "OverflowError: integer result does not fit in 64 bits"
I pys_floordiv(I a, I b) {
  if (!b) pys_fail(ZDE);
  if (b == -1) { if (a == INT64_MIN) pys_fail(OVF); return -a; }
  I q = a / b; return (a % b && (a < 0) != (b < 0)) ? q - 1 : q;
}
I pys_mod(I a, I b) {
  if (!b) pys_fail("ZeroDivisionError: integer modulo by zero");
  if (b == -1) return 0;
  I r = a % b; return (r && (r < 0) != (b < 0)) ? r + b : r;
}
I pys_pow(I a, I b) {
  if (b < 0) pys_fail("ValueError: negative exponent for int ** int");
  I r = 1, x = a;
  if (a == 0 || a == 1) return b ? a : 1;
  if (a == -1) return b & 1 ? -1 : 1;
  for (;;) {                                   /* |a| >= 2, so overflow comes within 63 steps */
    if ((b & 1) && __builtin_mul_overflow(r, x, &r)) pys_fail(OVF);
    if (!(b >>= 1)) return r;
    if (__builtin_mul_overflow(x, x, &x)) pys_fail(OVF);
  }
}
I pys_shl(I a, I b) {
  if (b < 0) pys_fail("ValueError: negative shift count");
  if (!a) return 0;
  I r = b > 63 ? 0 : (I)((uint64_t)a << b);
  if (b > 63 || r >> b != a) pys_fail(OVF);
  return r;
}
I pys_shr(I a, I b) { if (b < 0) pys_fail("ValueError: negative shift count"); return a >> (b > 63 ? 63 : b); }
double pys_fdiv(double a, double b) { if (b == 0) pys_fail("ZeroDivisionError: float division by zero"); return a / b; }
double pys_idiv(I a, I b) { if (!b) pys_fail("ZeroDivisionError: division by zero"); return (double)a / (double)b; }
static double pymod(double a, double b, double *q) {   /* CPython's float_divmod */
  double m = fmod(a, b), d = (a - m) / b;
  if (m) { if ((b < 0) != (m < 0)) { m += b; d -= 1; } } else m = copysign(0, b);
  if (d) { double f = floor(d); if (d - f > 0.5) f += 1; d = f; } else d = copysign(0, a / b);
  *q = d; return m;
}
double pys_fmod(double a, double b) { double q; if (b == 0) pys_fail("ZeroDivisionError: float modulo by zero"); return pymod(a, b, &q); }
double pys_ffloordiv(double a, double b) { double q; if (b == 0) pys_fail("ZeroDivisionError: float floor division by zero"); pymod(a, b, &q); return q; }
I pys_f2i(double d) {
  if (isnan(d)) pys_fail("ValueError: cannot convert float NaN to integer");
  if (isinf(d)) pys_fail("OverflowError: cannot convert float infinity to integer");
  if (!(d >= -9223372036854775808.0 && d < 9223372036854775808.0)) pys_fail("OverflowError: float too large for a 64-bit int");
  return (I)d;
}
I pys_round(double d) { return pys_f2i(nearbyint(d)); }
double pys_round_n(double x, I n) {           /* round(x, n): half-even on the exact decimal value */
  static char b[1500], o[1500];
  if (!isfinite(x) || n > 400) return x;
  if (n >= 0) { snprintf(b, sizeof b, "%.*f", (int)n, x); return strtod(b, 0); }
  int k = n < -400 ? 400 : (int)-n, len = snprintf(b, sizeof b, "%.1080f", fabs(x));
  int h = (int)(strchr(b, '.') - b) - k, up = 0, m = h;   /* keep h integer digits, drop k */
  if (h < 0) return copysign(0.0, x);
  if (b[h] != '5') up = b[h] > '5';
  else { up = -1; for (int i = h + 1; i < len; i++) if (b[i] > '0') { up = 1; break; } }
  memcpy(o, b, h);
  if (up < 0) up = h > 0 && (o[h - 1] - '0') % 2;          /* exact tie: round half to even */
  if (up) { int i = m - 1; while (i >= 0 && o[i] == '9') o[i--] = '0'; if (i >= 0) o[i]++; else { memmove(o + 1, o, m); o[0] = '1'; m++; } }
  if (!m) o[m++] = '0';
  memset(o + m, '0', k); o[m + k] = 0;
  return copysign(strtod(o, 0), x);
}
I pys_floor(double d) { return pys_f2i(floor(d)); }
I pys_ceil(double d) { return pys_f2i(ceil(d)); }

/* ---------- generic repr / equality / ordering driven by a type descriptor ----------
   i int, f float, b bool, s str, L<e> list, D<k><v> dict, T<n><e...> tuple */
static const char *skip(const char *d) {
  char c = *d++;
  if (c == 'L') return skip(d);
  if (c == 'D') return skip(skip(d));
  if (c == 'T') for (int n = *d++ - '0'; n > 0; n--) d = skip(d);
  return d;
}
static double dbl(I v) { double x; memcpy(&x, &v, 8); return x; }
static void repr_str(Buf *b, Str *s) {
  char q = memchr(s->s, '\'', s->len) && !memchr(s->s, '"', s->len) ? '"' : '\'', t[8];
  put(b, &q, 1);
  for (I i = 0; i < s->len; i++) {
    unsigned char c = s->s[i];
    if (c == q || c == '\\') { t[0] = '\\'; t[1] = c; put(b, t, 2); }
    else if (c == '\n') put(b, "\\n", 2);
    else if (c == '\r') put(b, "\\r", 2);
    else if (c == '\t') put(b, "\\t", 2);
    else if (c < 32 || c == 127) put(b, t, snprintf(t, 8, "\\x%02x", c));
    else put(b, (char *)&c, 1);
  }
  put(b, &q, 1);
}
static const char *repr(Buf *b, I v, const char *d) {
  switch (*d++) {
  case 'i': { char t[32]; put(b, t, snprintf(t, 32, "%lld", (long long)v)); return d; }
  case 'f': { Str *s = pys_str_float(dbl(v)); put(b, s->s, s->len); return d; }
  case 'b': put(b, v ? "True" : "False", v ? 4 : 5); return d;
  case 's': repr_str(b, (Str *)v); return d;
  case 'L': {
    List *l = (List *)v; put(b, "[", 1);
    for (I i = 0; i < l->len; i++) { if (i) put(b, ", ", 2); repr(b, l->a[i], d); }
    put(b, "]", 1); return skip(d);
  }
  case 'D': {
    Dict *m = (Dict *)v; const char *dv = skip(d); put(b, "{", 1);
    for (I i = 0; i < m->len; i++) {
      if (i) put(b, ", ", 2);
      repr(b, m->keys[i], d); put(b, ": ", 2); repr(b, m->vals[i], dv);
    }
    put(b, "}", 1); return skip(dv);
  }
  case 'T': {
    int n = *d++ - '0'; I *t = (I *)v; put(b, "(", 1);
    for (int i = 0; i < n; i++) { if (i) put(b, ", ", 2); d = repr(b, t[i], d); }
    put(b, n == 1 ? ",)" : ")", n == 1 ? 2 : 1); return d;
  }
  }
  return d;
}
Str *pys_repr(I v, Str *d) { Buf b = {0}; repr(&b, v, d->s); return done(&b); }
static I *slot(Dict *d, I k);
static int eqv(I a, I b, const char *d) {
  switch (*d) {
  case 'f': return dbl(a) == dbl(b);
  case 's': return pys_str_eq((Str *)a, (Str *)b);
  case 'L': {
    List *x = (List *)a, *y = (List *)b;
    if (x->len != y->len) return 0;
    for (I i = 0; i < x->len; i++) if (!eqv(x->a[i], y->a[i], d + 1)) return 0;
    return 1;
  }
  case 'D': {
    Dict *x = (Dict *)a, *y = (Dict *)b; const char *dv = skip(d + 1);
    if (x->len != y->len) return 0;
    for (I i = 0; i < x->len; i++) {
      I *c = y->cap ? slot(y, x->keys[i]) : 0;
      if (!c || !*c || !eqv(x->vals[i], y->vals[*c - 1], dv)) return 0;
    }
    return 1;
  }
  case 'T': {
    I *x = (I *)a, *y = (I *)b; const char *e = d + 2;
    for (int i = 0; i < d[1] - '0'; i++, e = skip(e)) if (!eqv(x[i], y[i], e)) return 0;
    return 1;
  }
  }
  return a == b;
}
I pys_eq(I a, I b, Str *d) { return eqv(a, b, d->s); }
static I cmpv(I a, I b, const char *d) {
  switch (*d) {
  case 'f': return (dbl(a) > dbl(b)) - (dbl(a) < dbl(b));
  case 's': return pys_str_cmp((Str *)a, (Str *)b);
  case 'L': {
    List *x = (List *)a, *y = (List *)b;
    for (I i = 0; i < x->len && i < y->len; i++) { I c = cmpv(x->a[i], y->a[i], d + 1); if (c) return c; }
    return (x->len > y->len) - (x->len < y->len);
  }
  case 'T': {
    I *x = (I *)a, *y = (I *)b; const char *e = d + 2;
    for (int i = 0; i < d[1] - '0'; i++, e = skip(e)) { I c = cmpv(x[i], y[i], e); if (c) return c; }
    return 0;
  }
  }
  return (a > b) - (a < b);
}
I pys_cmp(I a, I b, Str *d) { return cmpv(a, b, d->s); }

/* ---------- lists ---------- */
List *pys_list_new(I cap) {
  List *l = pys_alloc(sizeof(List));
  l->cap = cap > 4 ? cap : 4; l->a = pys_alloc(l->cap * 8); return l;
}
static void reserve(List *l, I n) {
  if (n <= l->cap) return;
  I c = l->cap * 2 > n ? l->cap * 2 : n; I *a = pys_alloc(c * 8);
  memcpy(a, l->a, l->len * 8); l->a = a; l->cap = c;
}
/* element access through a distinct struct type: TBAA then knows a store to an element
   never changes l->len or l->a, so LLVM hoists those loads out of loops */
typedef struct { I v; } Slot;
#define AT(l, i) (((Slot *)(l)->a)[i].v)
void pys_list_append(List *l, I v) { if (l->len == l->cap) reserve(l, l->len + 1); AT(l, l->len++) = v; }
I pys_list_get(List *l, I i) { return AT(l, idx(i, l->len, "IndexError: list index out of range")); }
void pys_list_set(List *l, I i, I v) { AT(l, idx(i, l->len, "IndexError: list assignment index out of range")) = v; }
I pys_list_pop(List *l, I i) {
  if (!l->len) pys_fail("IndexError: pop from empty list");
  i = idx(i, l->len, "IndexError: pop index out of range");
  I v = l->a[i]; memmove(l->a + i, l->a + i + 1, (l->len - i - 1) * 8); l->len--; return v;
}
void pys_list_insert(List *l, I i, I v) {
  if (i < 0 && (i += l->len) < 0) i = 0;
  if (i > l->len) i = l->len;
  reserve(l, l->len + 1); memmove(l->a + i + 1, l->a + i, (l->len - i) * 8); l->a[i] = v; l->len++;
}
void pys_list_extend(List *l, List *m) { I n = m->len; reserve(l, l->len + n); memcpy(l->a + l->len, m->a, n * 8); l->len += n; }
List *pys_list_slice(List *l, I lo, I hi) {
  span(&lo, &hi, l->len);
  List *r = pys_list_new(hi - lo); memcpy(r->a, l->a + lo, (hi - lo) * 8); r->len = hi - lo; return r;
}
List *pys_list_copy(List *l) { return pys_list_slice(l, NONE, NONE); }
void pys_list_clear(List *l) { l->len = 0; }
List *pys_list_add(List *a, List *b) { List *r = pys_list_new(a->len + b->len); pys_list_extend(r, a); pys_list_extend(r, b); return r; }
List *pys_list_mul(List *a, I n) {
  I m = a->len;
  if (n > 0 && m > (INT64_MAX >> 4) / n) pys_fail("MemoryError");
  List *r = pys_list_new(n > 0 ? m * n : 0);
  for (I i = 0; i < n; i++) memcpy(r->a + i * m, a->a, m * 8);
  r->len = n > 0 ? m * n : 0; return r;
}
I pys_list_find(List *l, I v, Str *d) { for (I i = 0; i < l->len; i++) if (eqv(l->a[i], v, d->s)) return i; return -1; }
I pys_list_index(List *l, I v, Str *d) { I i = pys_list_find(l, v, d); if (i < 0) pys_fail("ValueError: value is not in list"); return i; }
I pys_list_count(List *l, I v, Str *d) { I c = 0; for (I i = 0; i < l->len; i++) c += eqv(l->a[i], v, d->s); return c; }
void pys_list_remove(List *l, I v, Str *d) { pys_list_pop(l, pys_list_index(l, v, d)); }
void pys_list_reverse(List *l) { for (I i = 0, j = l->len - 1; i < j; i++, j--) { I t = l->a[i]; l->a[i] = l->a[j]; l->a[j] = t; } }
static void msort(I *a, I *t, I n, const char *d) {   /* stable merge sort, like Python's */
  if (n < 2) return;
  I h = n / 2, i = 0, j = h, k = 0;
  msort(a, t, h, d); msort(a + h, t, n - h, d);
  while (i < h && j < n) t[k++] = cmpv(a[j], a[i], d) < 0 ? a[j++] : a[i++];
  while (i < h) t[k++] = a[i++];
  memcpy(a, t, k * 8);
}
void pys_list_sort(List *l, Str *d) { msort(l->a, pys_alloc(l->len * 8), l->len, d->s); }
I pys_list_minmax(List *l, Str *d, I max) {
  if (!l->len) pys_fail("ValueError: arg is an empty sequence");
  I m = l->a[0];
  for (I i = 1; i < l->len; i++) if (max ? cmpv(l->a[i], m, d->s) > 0 : cmpv(l->a[i], m, d->s) < 0) m = l->a[i];
  return m;
}
I pys_any(List *l) { for (I i = 0; i < l->len; i++) if (l->a[i]) return 1; return 0; }
I pys_all(List *l) { for (I i = 0; i < l->len; i++) if (!l->a[i]) return 0; return 1; }
I pys_sum_int(List *l) { I s = 0; for (I i = 0; i < l->len; i++) if (__builtin_add_overflow(s, l->a[i], &s)) pys_fail(OVF); return s; }
double pys_sum_float(List *l) { double s = 0; for (I i = 0; i < l->len; i++) s += dbl(l->a[i]); return s; }
List *pys_range_list(I a, I b, I s) {
  List *l = pys_list_new(0);
  if (!s) pys_fail("ValueError: range() arg 3 must not be zero");
  for (I i = a; s > 0 ? i < b : i > b;) { pys_list_append(l, i); if (__builtin_add_overflow(i, s, &i)) break; }
  return l;
}
List *pys_str_list(Str *s) { List *l = pys_list_new(s->len); for (I i = 0; i < s->len; i++) pys_list_append(l, (I)pys_chr((unsigned char)s->s[i])); return l; }
Str *pys_str_join(Str *sep, List *l) {
  I n = 0;
  for (I i = 0; i < l->len; i++) n += ((Str *)l->a[i])->len + (i ? sep->len : 0);
  Str *r = pys_alloc(sizeof(Str) + n + 1); char *w = r->s; r->len = n;
  for (I i = 0; i < l->len; i++) {
    Str *s = (Str *)l->a[i];
    if (i) { memcpy(w, sep->s, sep->len); w += sep->len; }
    memcpy(w, s->s, s->len); w += s->len;
  }
  return r;
}
List *pys_str_split(Str *s, Str *sep) {
  List *l = pys_list_new(0); I i = 0, n = s->len;
  if (!sep) {
    for (;;) {
      while (i < n && ws(s->s[i])) i++;
      if (i >= n) return l;
      I j = i; while (j < n && !ws(s->s[j])) j++;
      pys_list_append(l, (I)pys_str(s->s + i, j - i)); i = j;
    }
  }
  if (!sep->len) pys_fail("ValueError: empty separator");
  for (I j; (j = find(s, sep, i)) >= 0; i = j + sep->len) pys_list_append(l, (I)pys_str(s->s + i, j - i));
  pys_list_append(l, (I)pys_str(s->s + i, n - i));
  return l;
}

/* ---------- dicts: compact ordered table + open-addressing index ---------- */
static uint64_t hsh(Dict *d, I k) {
  uint64_t h;
  if (d->kind) {
    Str *s = (Str *)k; h = 1469598103934665603ULL;
    for (I i = 0; i < s->len; i++) h = (h ^ (unsigned char)s->s[i]) * 1099511628211ULL;
  } else h = (uint64_t)k * 0x9E3779B97F4A7C15ULL;
  return h ^ (h >> 29);
}
static I *slot(Dict *d, I k) {
  I m = d->cap * 2 - 1;
  for (I i = hsh(d, k) & m;; i = (i + 1) & m) {
    I e = d->idx[i];
    if (!e || (d->kind ? pys_str_eq((Str *)d->keys[e - 1], (Str *)k) : d->keys[e - 1] == k)) return &d->idx[i];
  }
}
static void reindex(Dict *d) { memset(d->idx, 0, d->cap * 16); for (I e = 0; e < d->len; e++) *slot(d, d->keys[e]) = e + 1; }
static void grow(Dict *d) {
  I c = d->cap ? d->cap * 2 : 8, *k = pys_alloc(c * 8), *v = pys_alloc(c * 8);
  memcpy(k, d->keys, d->len * 8); memcpy(v, d->vals, d->len * 8);
  d->keys = k; d->vals = v; d->cap = c; d->idx = pys_alloc(c * 16); reindex(d);
}
Dict *pys_dict_new(I kind) { Dict *d = pys_alloc(sizeof(Dict)); d->kind = kind; return d; }
static _Noreturn void keyerr(Dict *d, I k) { Buf b = {0}; put(&b, "KeyError: ", 10); repr(&b, k, d->kind ? "s" : "i"); put(&b, "", 1); pys_fail(b.p); }
static I *look(Dict *d, I k) { I *c = d->cap ? slot(d, k) : 0; return c && *c ? c : 0; }
I pys_dict_has(Dict *d, I k) { return look(d, k) != 0; }
I pys_dict_getitem(Dict *d, I k) { I *c = look(d, k); if (!c) keyerr(d, k); return d->vals[*c - 1]; }
I pys_dict_get(Dict *d, I k, I dflt) { I *c = look(d, k); return c ? d->vals[*c - 1] : dflt; }
void pys_dict_set(Dict *d, I k, I v) {
  I *c = look(d, k);
  if (c) { d->vals[*c - 1] = v; return; }
  if (d->len == d->cap) grow(d);
  c = slot(d, k); d->keys[d->len] = k; d->vals[d->len] = v; *c = ++d->len;
}
I pys_dict_pop(Dict *d, I k) {
  I *c = look(d, k); if (!c) keyerr(d, k);
  I e = *c - 1, v = d->vals[e];
  memmove(d->keys + e, d->keys + e + 1, (d->len - e - 1) * 8);
  memmove(d->vals + e, d->vals + e + 1, (d->len - e - 1) * 8);
  d->len--; reindex(d); return v;
}
I pys_dict_setdefault(Dict *d, I k, I v) { I *c = look(d, k); if (c) return d->vals[*c - 1]; pys_dict_set(d, k, v); return v; }
I pys_dict_key(Dict *d, I i) { return d->keys[i]; }
I pys_dict_val(Dict *d, I i) { return d->vals[i]; }
void pys_dict_clear(Dict *d) { d->len = 0; if (d->cap) reindex(d); }
static List *col(Dict *d, I *a) { List *l = pys_list_new(d->len); memcpy(l->a, a, d->len * 8); l->len = d->len; return l; }
List *pys_dict_keys(Dict *d) { return col(d, d->keys); }
List *pys_dict_values(Dict *d) { return col(d, d->vals); }
List *pys_dict_items(Dict *d) {
  List *l = pys_list_new(d->len);
  for (I i = 0; i < d->len; i++) { I *t = pys_alloc(16); t[0] = d->keys[i]; t[1] = d->vals[i]; pys_list_append(l, (I)t); }
  return l;
}
Dict *pys_dict_copy(Dict *d) { Dict *r = pys_dict_new(d->kind); for (I i = 0; i < d->len; i++) pys_dict_set(r, d->keys[i], d->vals[i]); return r; }

/* ---------- formatting: f"{x:spec}" with [[fill]align][sign][0][width][,][.prec][type] ---------- */
Str *pys_format(I v, Str *desc, Str *spec) {
  const char *p = spec->s; char fill = ' ', align = 0, sign = '-', type = 0, num[1024], f[16];
  int width = 0, prec = -1, comma = 0, zero = 0, n;
  if (p[0] && (p[1] == '<' || p[1] == '>' || p[1] == '^')) { fill = p[0]; align = p[1]; p += 2; }
  else if (*p == '<' || *p == '>' || *p == '^') align = *p++;
  if (*p == '+' || *p == '-' || *p == ' ') sign = *p++;
  if (*p == '0') { zero = 1; p++; }
  while (*p >= '0' && *p <= '9') width = width * 10 + *p++ - '0';
  if (*p == ',') { comma = 1; p++; }
  if (*p == '.') { prec = 0; p++; while (*p >= '0' && *p <= '9') prec = prec * 10 + *p++ - '0'; }
  if (*p) type = *p++;
  if (*p) pys_fail("ValueError: invalid format specifier");
  char d = desc->s[0];
  Str *body;
  if (prec > 100) prec = 100;
  if (d == 's' || (d != 'i' && d != 'f' && d != 'b')) {
    body = d == 's' ? (Str *)v : pys_repr(v, desc);
    if (prec >= 0 && prec < body->len) body = pys_str(body->s, prec);
  } else {
    int isf = d == 'f' || (type && strchr("eEfFgG%", type));
    double x = d == 'f' ? dbl(v) : (double)v;
    if (isf && !type && prec < 0) body = pys_str_float(x);
    else if (isf) {
      char t = type ? type : 'g';
      if (t == '%') x *= 100;
      snprintf(f, 16, "%%.%d%c", prec < 0 ? 6 : prec, t == '%' ? 'f' : t);
      n = snprintf(num, 1000, f, x);
      if (t == '%') num[n++] = '%';
      if (!type && isfinite(x) && !strpbrk(num, ".e")) { num[n++] = '.'; num[n++] = '0'; }
      body = pys_str(num, n);
    } else {
      const char *fm = type == 'x' ? "%llx" : type == 'X' ? "%llX" : type == 'o' ? "%llo" : "%lld";
      if (type && !strchr("dxXoc", type)) pys_fail("ValueError: unknown format code for int");
      body = type == 'c' ? pys_chr(v) : pys_str(num, snprintf(num, 1000, fm, (long long)(type && type != 'd' && v < 0 ? -v : v)));
      if (type && type != 'd' && type != 'c' && v < 0) body = pys_str_add(cstr("-"), body);
    }
    if (comma) {
      Buf b = {0}; I s = body->s[0] == '-', e = s;
      while (e < body->len && body->s[e] >= '0' && body->s[e] <= '9') e++;
      put(&b, body->s, s);
      for (I i = s; i < e; i++) { put(&b, body->s + i, 1); if ((e - i - 1) % 3 == 0 && i < e - 1) put(&b, ",", 1); }
      put(&b, body->s + e, body->len - e); body = done(&b);
    }
    if (sign != '-' && body->s[0] != '-') body = pys_str_add(cstr(sign == '+' ? "+" : " "), body);
    if (!align) align = zero ? '=' : '>';
    if (zero && fill == ' ') fill = '0';
  }
  if (!align) align = '<';
  if (body->len >= width) return body;
  Str *r = pys_alloc(sizeof(Str) + width + 1); r->len = width; memset(r->s, fill, width);
  I gap = width - body->len, at = align == '<' ? 0 : align == '^' ? gap / 2 : gap;
  if (align == '=') {                                  /* pad after the sign */
    I s = body->s[0] == '-' || body->s[0] == '+' || body->s[0] == ' ';
    memcpy(r->s, body->s, s); memcpy(r->s + s + gap, body->s + s, body->len - s);
  } else memcpy(r->s + at, body->s, body->len);
  return r;
}

/* ---------- I/O and process ---------- */
static List *args;
void pys_init(int argc, char **argv) { args = pys_list_new(argc); for (int i = 0; i < argc; i++) pys_list_append(args, (I)cstr(argv[i])); }
List *pys_argv(void) { return args; }
void pys_write(Str *s, I fd) { fwrite(s->s, 1, s->len, fd == 2 ? stderr : stdout); }
void pys_flush(void) { fflush(stdout); }
I pys_out(Str *s) { pys_write(s, 1); return s->len; }
I pys_err(Str *s) { pys_write(s, 2); return s->len; }
Str *pys_input(Str *prompt) {
  char *line = 0; size_t cap = 0;
  pys_write(prompt, 1); fflush(stdout);
  ssize_t n = getline(&line, &cap, stdin);
  if (n < 0) pys_fail("EOFError: EOF when reading a line");
  if (n && line[n - 1] == '\n') n--;
  Str *s = pys_str(line, n); free(line); return s;
}
void *pys_open(Str *path, Str *mode) {
  FILE *f = fopen(path->s, mode->s);
  if (!f) badnum("FileNotFoundError: No such file or directory: '", path);
  return f;
}
Str *pys_file_read(FILE *f) { Buf b = {0}; char t[1 << 16]; size_t n; while ((n = fread(t, 1, sizeof t, f)) > 0) put(&b, t, n); return done(&b); }
Str *pys_file_readline(FILE *f) {
  Buf b = {0}; int c;
  while ((c = fgetc(f)) != EOF) { char ch = c; put(&b, &ch, 1); if (c == '\n') break; }
  return done(&b);
}
I pys_file_write(FILE *f, Str *s) { fwrite(s->s, 1, s->len, f); return s->len; }
void pys_file_close(FILE *f) { fclose(f); }
void pys_exit(I c) { exit((int)c); }
I pys_system(Str *c) { fflush(stdout); return system(c->s); }
I pys_getpid(void) { return getpid(); }
I pys_exists(Str *p) { return access(p->s, F_OK) == 0; }
Str *pys_getenv(Str *k, Str *dflt) { char *v = getenv(k->s); return v ? cstr(v) : dflt; }
