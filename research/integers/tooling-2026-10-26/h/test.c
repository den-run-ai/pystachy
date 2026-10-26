/* Differential test: the edited mpz core (new_*) against main's (old_*), which earlier
   CPython-recorded tests validate. Any difference in value, digits or error text fails. */
#include "common.h"
#include "api.h"
DECL(old_)
DECL(new_)
typedef struct { I size; uint32_t d[]; } Z;
#define ZMASK ((UINT32_C(1) << 30) - 1)

static void **allocs; static I nallocs, capallocs;
void *pys_alloc_atomic(I n) {
  void *p = calloc(1, n ? n : 1); if (!p) { perror("calloc"); exit(2); }
  if (nallocs == capallocs) { capallocs = capallocs * 2 + 1024; allocs = realloc(allocs, capallocs * sizeof *allocs); }
  allocs[nallocs++] = p; return p;
}
static void release(void) { for (I i = 0; i < nallocs; i++) free(allocs[i]); nallocs = 0; }
static jmp_buf jb; static char failmsg[600];
_Noreturn void pys_fail(const char *m) { snprintf(failmsg, sizeof failmsg, "%s", m); longjmp(jb, 1); }

static uint64_t rs = 88172645463325252ULL;
static uint64_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }
static I rint_(I n) { return n <= 0 ? 0 : (I)(rnd() % (uint64_t)n); }

static I pick_size(void) {
  static const I special[] = {0, 1, 2, 3, 35, 69, 70, 71, 72, 139, 140, 141, 142, 210, 211, 280, 281, 477, 478};
  switch (rint_(6)) {
  case 0: return special[rint_(sizeof special / sizeof *special)];
  case 1: return 1 + rint_(8);
  case 2: return rint_(80);
  case 3: return 60 + rint_(200);
  case 4: return 140 + rint_(600);
  default: return rint_(2000);
  }
}
static Z *mk(I n) {
  Z *z = pys_alloc_atomic(sizeof(Z) + (n ? n : 1) * 4);
  int pat = (int)rint_(7);
  for (I i = 0; i < n; i++) {
    uint32_t v = (uint32_t)rnd() & ZMASK;
    if (pat == 1) v = ZMASK;
    else if (pat == 2) v = rint_(8) ? 0 : v;
    else if (pat == 3) v = rint_(3) ? ZMASK : 0;
    else if (pat == 4) v = (i == n - 1 || i == 0) ? v : 0;
    else if (pat == 5) v = rint_(4) ? ZMASK : (uint32_t)rint_(3);
    z->d[i] = v;
  }
  if (n && !z->d[n - 1]) z->d[n - 1] = 1 + (uint32_t)rint_(ZMASK);
  z->size = rint_(2) ? -n : n;
  return z;
}
static int same(Z *a, Z *b) {
  if (a->size != b->size) return 0;
  I n = a->size < 0 ? -a->size : a->size;
  return !memcmp(a->d, b->d, n * 4);
}
static I fails;
static void report(const char *what, I k) { if (fails++ < 20) fprintf(stderr, "MISMATCH %s case %lld\n", what, (long long)k); }

/* run expression E with old_ and new_ and compare values or error text */
#define CHECKV(name, k, CALL) do { \
    void *ro = 0, *rn = 0; char eo[600] = "", en[600] = ""; \
    if (!setjmp(jb)) { ro = old_##CALL; } else { snprintf(eo, sizeof eo, "%s", failmsg); } \
    if (!setjmp(jb)) { rn = new_##CALL; } else { snprintf(en, sizeof en, "%s", failmsg); } \
    if (strcmp(eo, en) || (!*eo && !same(ro, rn))) { report(name, k); fprintf(stderr, "  old err [%s] new err [%s]\n", eo, en); } \
  } while (0)

static Str *mkstr(const char *p, I n) { Str *s = pys_alloc_atomic(sizeof(Str) + n + 1); s->len = n; memcpy(s->s, p, n); return s; }

int main(int argc, char **argv) {
  I iters = argc > 1 ? atoll(argv[1]) : 2000;
  if (argc > 2) rs = (uint64_t)atoll(argv[2]) * 2654435761u + 1;
  I checks = 0;
  for (I k = 0; k < iters; k++) {
    I an = pick_size(), bn = pick_size();
    if (rint_(5) == 0 && an > 70) bn = 2 * an + rint_(3 * an + 1);   /* lopsided */
    Z *a = mk(an), *b = rint_(10) ? mk(bn) : a;
    for (I op = 0; op <= 7; op++) { CHECKV("binop", k * 8 + op, binop(a, b, op)); checks++; }
    CHECKV("square", k, binop(a, a, 2)); checks++;
    for (I op = 0; op <= 2; op++) { CHECKV("unary", k, unary(a, op)); checks++; }
    I sh = rint_(4) ? rint_(200) : rint_(5000);
    CHECKV("lshift", k, shift(a, sh, 0)); CHECKV("rshift", k, shift(a, sh, 1)); checks += 2;
    if (an <= 40) { I e = rint_(40); CHECKV("pow", k, pow(a, e)); checks++; }
    if (old_cmp(a, b) != new_cmp(a, b)) report("cmp", k);
    if (old_hash(a) != new_hash(a)) report("hash", k);
    if (old_bit_length(a) != new_bit_length(a)) report("bit_length", k);
    checks += 3;
    /* decimal text: compare formatting, then parse the text back with both */
    {
      Str *so = 0, *sn = 0; char eo[600] = "", en[600] = "";
      if (!setjmp(jb)) so = old_str(a); else snprintf(eo, sizeof eo, "%s", failmsg);
      if (!setjmp(jb)) sn = new_str(a); else snprintf(en, sizeof en, "%s", failmsg);
      if (strcmp(eo, en) || (!*eo && (so->len != sn->len || memcmp(so->s, sn->s, so->len) || so->chars1 != sn->chars1))) report("str", k);
      if (!*eo) { CHECKV("parse10", k, from_str(so, 10)); CHECKV("parse0", k, from_str(so, 0)); checks += 2; }
      checks++;
    }
    /* random digit strings in random bases, with underscores, prefixes, signs, spaces and errors */
    for (int t = 0; t < 4; t++) {
      I base = rint_(4) ? 2 + rint_(35) : (rint_(2) ? 10 : 0);
      I nd = rint_(3) ? rint_(60) : rint_(6000), m = 0;
      char *buf = malloc(2 * nd + 16);
      if (rint_(4) == 0) buf[m++] = ' ';
      if (rint_(3) == 0) buf[m++] = rint_(2) ? '-' : '+';
      I eb = base ? base : 10;
      if ((base == 0 || base == 16) && rint_(3) == 0) { buf[m++] = '0'; buf[m++] = 'x'; eb = 16; }
      else if ((base == 0 || base == 2) && rint_(4) == 0) { buf[m++] = '0'; buf[m++] = 'b'; eb = 2; }
      else if ((base == 0 || base == 8) && rint_(4) == 0) { buf[m++] = '0'; buf[m++] = 'O'; eb = 8; }
      if (eb != (base ? base : 10) && rint_(2)) buf[m++] = '_';
      for (I i = 0; i < nd; i++) {
        I dv = rint_(eb);
        if (rint_(500) == 0) dv = rint_(36);           /* occasionally invalid for the base */
        buf[m++] = dv < 10 ? '0' + dv : (rint_(2) ? 'a' : 'A') + dv - 10;
        if (i + 1 < nd && rint_(7) == 0) buf[m++] = '_';
        if (rint_(3000) == 0) buf[m++] = '_';          /* occasionally a double or trailing underscore */
      }
      if (rint_(4) == 0) buf[m++] = '\t';
      Str *s = mkstr(buf, m); free(buf);
      CHECKV("parse", k * 4 + t, from_str(s, base)); checks++;
    }
    release();
  }
  printf("%lld checks, %lld mismatches\n", (long long)checks, (long long)fails);
  return fails != 0;
}
