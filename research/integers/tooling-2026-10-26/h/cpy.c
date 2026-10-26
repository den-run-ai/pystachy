/* Reads commands on stdin and answers with the edited core (new_*), for comparison with CPython:
   "P base text" parses text (prints hex or "E message"), "F hex" formats a value given in hex
   (built here by bit packing, not by the core), "M op hexa hexb" runs binop op. */
#include "common.h"
#include "api.h"
DECL(new_)
typedef struct { I size; uint32_t d[]; } Z;
void *pys_alloc_atomic(I n) { void *p = calloc(1, n ? n : 1); if (!p) exit(2); return p; }
static jmp_buf jb; static char failmsg[600];
_Noreturn void pys_fail(const char *m) { snprintf(failmsg, sizeof failmsg, "%s", m); longjmp(jb, 1); }
static Z *fromhex(const char *h) {
  int neg = *h == '-'; if (neg) h++;
  I n = strlen(h), limbs = (n * 4 + 29) / 30 + 1; Z *z = pys_alloc_atomic(sizeof(Z) + limbs * 4);
  uint64_t acc = 0; int have = 0; I k = 0;
  for (I i = n; i > 0; i--) {
    char c = h[i - 1]; int v = c <= '9' ? c - '0' : (c | 32) - 'a' + 10;
    acc |= (uint64_t)v << have; have += 4;
    if (have >= 30) { z->d[k++] = acc & ((1u << 30) - 1); acc >>= 30; have -= 30; }
  }
  if (have) z->d[k++] = (uint32_t)acc;
  while (k && !z->d[k - 1]) k--;
  z->size = neg ? -k : k; return z;
}
static void printhex(Z *z) {
  I n = z->size < 0 ? -z->size : z->size;
  if (!n) { puts("0"); return; }
  /* bits from the top, 4 at a time */
  I bits = (n - 1) * 30; uint32_t t = z->d[n - 1]; while (t) { bits++; t >>= 1; }
  char *out = malloc(bits / 4 + 4); I o = 0; int started = 0;
  if (z->size < 0) out[o++] = '-';
  for (I b = (bits + 3) / 4 * 4 - 4; b >= 0; b -= 4) {
    int v = 0;
    for (int j = 3; j >= 0; j--) { I bit = b + j, limb = bit / 30; v = v << 1 | (limb < n ? (z->d[limb] >> (bit % 30)) & 1 : 0); }
    if (v || started) { out[o++] = "0123456789abcdef"[v]; started = 1; }
  }
  out[o] = 0; puts(out); free(out);
}
int main(void) {
  static char line[1 << 22];
  while (fgets(line, sizeof line, stdin)) {
    line[strcspn(line, "\n")] = 0;
    if (line[0] == 'P') {
      char *sp = strchr(line + 2, ' '); I base = atoll(line + 2); char *text = sp + 1;
      I n = strlen(text); Str *s = pys_alloc_atomic(sizeof(Str) + n + 1); s->len = n; memcpy(s->s, text, n);
      if (!setjmp(jb)) printhex(new_from_str(s, base)); else printf("E %s\n", failmsg);
    } else if (line[0] == 'F') {
      Z *z = fromhex(line + 2);
      if (!setjmp(jb)) { Str *s = new_str(z); printf("%.*s\n", (int)s->len, s->s); } else printf("E %s\n", failmsg);
    } else if (line[0] == 'S') {   /* square: the same handle twice */
      Z *x = fromhex(line + 2);
      if (!setjmp(jb)) printhex(new_binop(x, x, 2)); else printf("E %s\n", failmsg);
    } else if (line[0] == 'M') {
      I op = line[2] - '0'; char *b = strchr(line + 4, ' '); *b = 0;
      Z *x = fromhex(line + 4), *y = fromhex(b + 1);
      if (!setjmp(jb)) printhex(new_binop(x, y, op)); else printf("E %s\n", failmsg);
    }
    fflush(stdout);
  }
  return 0;
}
