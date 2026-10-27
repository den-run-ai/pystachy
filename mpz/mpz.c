/*
 * This file is part of the MicroPython project, http://micropython.org/
 *
 * The MIT License (MIT)
 *
 * Copyright (c) 2013, 2014 Damien P. George
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

/* Pystachy port: immutable, single-allocation base-2^30 values, with the
   MicroPython mpn multiply-add adapted to them. This file is included by
   runtime.c after its numeric parsing helpers. No MPZ object contains a pointer;
   class fields and containers root the handle. Only fresh, unpublished
   result/scratch objects are mutated.
   Parsing, decimal formatting, addition, subtraction, multiplication and
   division follow CPython 3.13.16's Objects/longobject.c (Python Software
   Foundation License Version 2; see THIRD_PARTY_NOTICES and mpz/README.md):
   linear power-of-two bases, digit groups in other bases, Knuth's single-pass
   conversion to base 10^9, schoolbook products with a squaring loop, Karatsuba
   multiplication and Knuth's Algorithm D, in indexed loops that never form a
   pointer before an array. */

#define ZBITS 30
#define ZBASE (UINT64_C(1) << ZBITS)
#define ZMASK (ZBASE - 1)
typedef struct { I size; uint32_t d[]; } Mpz; /* sign in size; zero has size 0 */
static const Mpz mpz_zero = {0}; /* immutable and pointer-free: no collector root */

static I zn(const Mpz *a) { return a->size < 0 ? -a->size : a->size; }
static Mpz *zalloc(I n) {
  /* Keep bit_length, digit-count estimates, and allocation arithmetic in I. */
  if (n < 0 || n > (INT64_MAX - 64) / ZBITS) pys_fail("OverflowError: mpz is too large");
  return pys_alloc_atomic(sizeof(Mpz) + n * sizeof(uint32_t));
}
static void ztrim(Mpz *a, I n, int negative) {
  while (n && !a->d[n - 1]) n--;
  a->size = negative ? -n : n;
}
static Mpz *zcopy(const Mpz *a, I extra) {
  I n = zn(a); Mpz *r = zalloc(n + extra);
  memcpy(r->d, a->d, n * sizeof(uint32_t)); r->size = a->size;
  return r;
}
static int zcmpmag(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b);
  if (an != bn) return an < bn ? -1 : 1;
  for (I i = an; i; i--) if (a->d[i - 1] != b->d[i - 1]) return a->d[i - 1] < b->d[i - 1] ? -1 : 1;
  return 0;
}
I pys_mpz_cmp(void *ap, void *bp) {
  Mpz *a = ap, *b = bp;
  if ((a->size < 0) != (b->size < 0)) return a->size < 0 ? -1 : 1;
  I c = zcmpmag(a, b); return a->size < 0 ? -c : c;
}
void *pys_mpz_from_int(I value) {
  if (!value) return (void *)&mpz_zero;
  I n = 0; uint64_t u = value < 0 ? 0 - (uint64_t)value : (uint64_t)value;
  for (uint64_t v = u; v; v >>= ZBITS) n++;
  Mpz *r = zalloc(n);
  for (I i = 0; i < n; i++) { r->d[i] = u & ZMASK; u >>= ZBITS; }
  r->size = value < 0 ? -n : n; return r;
}
/* In-place one-digit multiply/add, only on private scratch with one spare digit.
   Adapted from MicroPython mpn_mul_dig_add_dig. */
static void zmuladd(Mpz *a, uint32_t mul, uint32_t add) {
  I n = zn(a); uint64_t carry = add;
  for (I i = 0; i < n; i++) {
    carry += (uint64_t)a->d[i] * mul; a->d[i] = carry & ZMASK; carry >>= ZBITS;
  }
  if (carry) a->d[n++] = carry;
  a->size = n;
}
void *pys_mpz_from_str(Str *s, I base) {
  if (base != 0 && (base < 2 || base > 36)) pys_fail("ValueError: int() base must be >= 2 and <= 36, or 0");
  /* Reuse int's Unicode decimal-digit/space normalization and literal diagnostics. */
  Str *t = asciinum(s); I lo = 0, hi = t->len, original = base;
  while (lo < hi && aws(t->s[lo])) lo++;
  while (hi > lo && aws(t->s[hi - 1])) hi--;
  int negative = 0, old_octal = 0, prev = 0;
  if (lo < hi && (t->s[lo] == '+' || t->s[lo] == '-')) negative = t->s[lo++] == '-';
  if (hi - lo >= 2 && t->s[lo] == '0') {
    int c = t->s[lo + 1] | 32, pb = c == 'x' ? 16 : c == 'o' ? 8 : c == 'b' ? 2 : 0;
    if (pb && (base == 0 || base == pb)) { base = pb; lo += 2; if (lo < hi && t->s[lo] == '_') lo++; }
  }
  if (!base) { base = 10; old_octal = lo < hi && t->s[lo] == '0'; }
  I digits = 0; int nonzero = 0;
  for (I i = lo; i < hi; i++) {
    int c = (unsigned char)t->s[i], d = digitv(c);
    if (c == '_' && prev == 1) { prev = 2; continue; }
    if (d >= base) badlit("ValueError: invalid literal for int()", original, s);
    digits++; prev = 1; nonzero |= d != 0;
  }
  if (!digits || prev != 1) badlit("ValueError: invalid literal for int()", original, s);
  if ((base & (base - 1)) && digits > 4300)
    failf("ValueError: Exceeds the limit (4300 digits) for integer string conversion: value has %lld digits; "
          "use sys.set_int_max_str_digits() to increase the limit", (long long)digits);
  /* CPython rejects a nonzero base-0 literal with a leading zero after the digit limit */
  if (old_octal && nonzero) badlit("ValueError: invalid literal for int()", original, s);
  Mpz *r;
  if (!(base & (base - 1))) {
    /* A power-of-two base packs bits from the last digit in linear time, as CPython's
       long_from_binary_base does. */
    int bits = 0; while (1 << bits < base) bits++;
    r = zalloc((digits * bits + ZBITS - 1) / ZBITS);
    uint64_t acc = 0; int have = 0; I n = 0;
    for (I i = hi; i > lo; i--) {
      if (t->s[i - 1] == '_') continue;
      acc |= (uint64_t)digitv(t->s[i - 1]) << have; have += bits;
      if (have >= ZBITS) { r->d[n++] = acc & ZMASK; acc >>= ZBITS; have -= ZBITS; }
    }
    if (have) r->d[n++] = (uint32_t)acc;
    ztrim(r, n, negative); return r;
  }
  /* Other bases multiply-add the largest group of digits below 2^30 at once (nine decimal
     digits), as CPython's long_from_non_binary_base does. A group's value and multiplier
     stay below 2^30, so zmuladd's carry stays one digit. */
  uint32_t width = 1, scale = (uint32_t)base;
  while ((uint64_t)scale * base < ZBASE) { scale *= base; width++; }
  /* Each digit contributes at most six bits; ceil(digits/5) is sufficient. */
  r = zalloc(digits / 5 + 2);
  for (I i = lo; i < hi;) {
    uint32_t group = 0, mul = 1;
    for (uint32_t k = 0; k < width && i < hi; i++)
      if (t->s[i] != '_') { group = group * base + digitv(t->s[i]); mul *= base; k++; }
    zmuladd(r, mul, group);
  }
  if (negative) r->size = -r->size;
  return r;
}
/* Magnitude sum, as CPython's x_add: the shorter operand's digits, then the carry
   through the longer one's. */
static Mpz *zaddmag(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b);
  if (an < bn) { const Mpz *t = a; a = b; b = t; I u = an; an = bn; bn = u; }
  Mpz *r = zalloc(an + 1); uint32_t carry = 0; I i = 0;
  for (; i < bn; i++) { carry += a->d[i] + b->d[i]; r->d[i] = carry & ZMASK; carry >>= ZBITS; }
  for (; i < an; i++) { carry += a->d[i]; r->d[i] = carry & ZMASK; carry >>= ZBITS; }
  r->d[an] = carry; ztrim(r, an + 1, 0); return r;
}
/* Magnitude difference |a| - |b| for |a| >= |b|, as CPython's x_sub: a borrow wraps a
   digit's uint32_t, setting bit ZBITS. */
static Mpz *zsubmag(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b); Mpz *r = zalloc(an); uint32_t borrow = 0; I i = 0;
  for (; i < bn; i++) { borrow = a->d[i] - b->d[i] - borrow; r->d[i] = borrow & ZMASK; borrow = borrow >> ZBITS & 1; }
  for (; i < an; i++) { borrow = a->d[i] - borrow; r->d[i] = borrow & ZMASK; borrow = borrow >> ZBITS & 1; }
  ztrim(r, an, 0); return r;
}
static Mpz *zadd(const Mpz *a, const Mpz *b, int subtract) {
  int na = a->size < 0, nb = (b->size < 0) ^ subtract;
  Mpz *r;
  if (na == nb) r = zaddmag(a, b);
  else if (zcmpmag(a, b) >= 0) r = zsubmag(a, b);
  else { r = zsubmag(b, a); na = nb; }
  if (na) r->size = -r->size;
  return r;
}
/* x[0, m) += y[0, n) for m >= n, and x[0, m) -= y[0, n), as CPython's v_iadd and v_isub:
   a carry or borrow out of x[m - 1] is dropped (arithmetic modulo 2^(30m)). */
static void zvadd(uint32_t *x, I m, const uint32_t *y, I n) {
  uint32_t carry = 0; I i = 0;
  for (; i < n; i++) { carry += x[i] + y[i]; x[i] = carry & ZMASK; carry >>= ZBITS; }
  for (; carry && i < m; i++) { carry += x[i]; x[i] = carry & ZMASK; carry >>= ZBITS; }
}
static void zvsub(uint32_t *x, I m, const uint32_t *y, I n) {
  uint32_t borrow = 0; I i = 0;
  for (; i < n; i++) { borrow = x[i] - y[i] - borrow; x[i] = borrow & ZMASK; borrow = borrow >> ZBITS & 1; }
  for (; borrow && i < m; i++) { borrow = x[i] - borrow; x[i] = borrow & ZMASK; borrow = borrow >> ZBITS & 1; }
}
/* Schoolbook product of magnitudes, as CPython's x_mul. A 30-bit digit product plus
   one result digit and carry fits uint64_t without wrapping. The same operand twice
   is squared (HAC 14.16): each cross product is added once, doubled, which keeps the
   carry below 2^32 and leaves at most one more carry into a digit that is still 0. */
static Mpz *zmulmag(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b); Mpz *r = zalloc(an + bn); uint32_t *z = r->d;
  if (a == b) {
    for (I i = 0; i < an; i++) {
      uint64_t f = a->d[i], carry = z[2 * i] + f * f; I k = 2 * i;
      z[k++] = carry & ZMASK; carry >>= ZBITS; f <<= 1;
      for (I j = i + 1; j < an; j++) { carry += z[k] + a->d[j] * f; z[k++] = carry & ZMASK; carry >>= ZBITS; }
      if (carry) {
        carry += z[k]; z[k] = carry & ZMASK; carry >>= ZBITS;
        if (carry) z[k + 1] = (uint32_t)carry;
      }
    }
  } else {
    for (I i = 0; i < an; i++) {
      uint64_t f = a->d[i], carry = 0; I k = i;
      for (I j = 0; j < bn; j++) { carry += z[k] + b->d[j] * f; z[k++] = carry & ZMASK; carry >>= ZBITS; }
      z[k] = (uint32_t)carry;
    }
  }
  ztrim(r, an + bn, 0); return r;
}
/* CPython's KARATSUBA_CUTOFF for 30-bit digits: schoolbook multiplication below it
   (twice it for squares) beats splitting. */
#define ZKARATSUBA 70
/* |n| = high * 2^(30 * size) + low, as CPython's kmul_split. */
static void zsplit(const Mpz *n, I size, Mpz **high, Mpz **low) {
  I nn = zn(n), lo = nn < size ? nn : size, hi = nn - lo;
  Mpz *h = zalloc(hi), *l = zalloc(lo);
  memcpy(l->d, n->d, lo * sizeof(uint32_t)); memcpy(h->d, n->d + lo, hi * sizeof(uint32_t));
  ztrim(h, hi, 0); ztrim(l, lo, 0); *high = h; *low = l;
}
static Mpz *zkmul(const Mpz *a, const Mpz *b);
/* |b| has at least twice |a|'s digits and |a| more than ZKARATSUBA: multiply a by
   a-sized slices of b, so that zkmul splits balanced operands (CPython's
   k_lopsided_mul). A slice keeps its zero high digits; only its product is read. */
static Mpz *zkmul_lopsided(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b), n = an + bn;
  Mpz *r = zalloc(n), *slice = zalloc(an);
  for (I done = 0; done < bn;) {
    I use = bn - done < an ? bn - done : an;
    memcpy(slice->d, b->d + done, use * sizeof(uint32_t)); slice->size = use;
    Mpz *p = zkmul(a, slice);
    zvadd(r->d + done, n - done, p->d, zn(p));
    done += use;
  }
  ztrim(r, n, 0); return r;
}
/* Karatsuba multiplication of magnitudes (Knuth 4.3.3), as CPython's k_mul: with
   X = 2^(30 * shift), (ah*X + al)(bh*X + bl) = ah*bh*X^2 + al*bl
   + ((ah + al)(bh + bl) - ah*bh - al*bl)*X takes three half-size products. Each
   product fits its place in the result, which is computed modulo 2^(30 * n), so a
   borrow or carry out of its top digit is dropped (CPython's comment explains). */
static Mpz *zkmul(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b);
  if (an > bn) { const Mpz *t = a; a = b; b = t; I u = an; an = bn; bn = u; }
  if (an <= (a == b ? 2 * ZKARATSUBA : ZKARATSUBA)) return an ? zmulmag(a, b) : (Mpz *)&mpz_zero;
  if (2 * an <= bn) return zkmul_lopsided(a, b);
  I shift = bn >> 1, n = an + bn;
  Mpz *ah, *al, *bh, *bl;
  zsplit(a, shift, &ah, &al);
  if (a == b) { bh = ah; bl = al; } else zsplit(b, shift, &bh, &bl);
  Mpz *r = zalloc(n), *t1 = zkmul(ah, bh), *t2 = zkmul(al, bl);
  memcpy(r->d + 2 * shift, t1->d, zn(t1) * sizeof(uint32_t));
  memcpy(r->d, t2->d, zn(t2) * sizeof(uint32_t));
  zvsub(r->d + shift, n - shift, t2->d, zn(t2));
  zvsub(r->d + shift, n - shift, t1->d, zn(t1));
  Mpz *s1 = zaddmag(ah, al), *s2 = a == b ? s1 : zaddmag(bh, bl), *t3 = zkmul(s1, s2);
  zvadd(r->d + shift, n - shift, t3->d, zn(t3));
  ztrim(r, n, 0); return r;
}
static Mpz *zmul(const Mpz *a, const Mpz *b) {
  if (!a->size || !b->size) return (Mpz *)&mpz_zero;
  Mpz *r = zkmul(a, b);   /* nonzero operands give a fresh, unshared product */
  if ((a->size < 0) != (b->size < 0)) r->size = -r->size;
  return r;
}
/* Long division of magnitudes |a| >= |b| with |b| of at least two digits, as CPython's
   x_divrem (Knuth 4.3.1 Algorithm D). Both operands are shifted left so that the divisor's
   top digit has its high bit set; each quotient digit is estimated from the dividend's top
   two digits and corrected with the divisor's second digit, so it is at most one too large,
   which one add-back fixes. q has room for one more digit; r gets the remainder. */
static void zdivrem(const Mpz *a, const Mpz *b, Mpz *q, Mpz *r) {
  I an = zn(a), bn = zn(b), vn = an;
  int d = 0; for (uint32_t top = b->d[bn - 1]; !(top & (UINT32_C(1) << (ZBITS - 1))); top <<= 1) d++;
  uint32_t *w = r->d, *v = pys_alloc_atomic((an + 1) * sizeof(uint32_t)), carry = 0;
  for (I i = 0; i < bn; i++) { uint64_t x = (uint64_t)b->d[i] << d | carry; w[i] = x & ZMASK; carry = x >> ZBITS; }
  carry = 0;
  for (I i = 0; i < an; i++) { uint64_t x = (uint64_t)a->d[i] << d | carry; v[i] = x & ZMASK; carry = x >> ZBITS; }
  if (carry || v[an - 1] >= w[bn - 1]) v[vn++] = carry;
  I k = vn - bn; uint32_t wm1 = w[bn - 1], wm2 = w[bn - 2];
  for (I j = k; j--;) {   /* divide v[j, j + bn] by w: one quotient digit */
    uint32_t vtop = v[j + bn];
    uint64_t vv = (uint64_t)vtop << ZBITS | v[j + bn - 1];
    uint32_t qd = (uint32_t)(vv / wm1), rem = (uint32_t)(vv % wm1);
    while ((uint64_t)wm2 * qd > ((uint64_t)rem << ZBITS | v[j + bn - 2])) {
      qd--; rem += wm1;
      if (rem >= ZBASE) break;
    }
    int32_t zhi = 0;   /* v[j, j + bn) -= qd * w, with a signed carry in [-qd, 0] */
    for (I i = 0; i < bn; i++) {
      int64_t z = (int64_t)v[j + i] + zhi - (int64_t)qd * w[i];
      v[j + i] = (uint32_t)z & ZMASK; zhi = (int32_t)(z >> ZBITS);
    }
    if ((int32_t)vtop + zhi < 0) {   /* qd was one too large: add w back */
      uint32_t c = 0;
      for (I i = 0; i < bn; i++) { c += v[j + i] + w[i]; v[j + i] = c & ZMASK; c >>= ZBITS; }
      qd--;
    }
    q->d[j] = qd;
  }
  ztrim(q, k, 0);
  carry = 0;   /* the remainder is v[0, bn) shifted back right */
  for (I i = bn; i; i--) {
    uint32_t x = v[i - 1];
    w[i - 1] = (x >> d | carry) & ZMASK; carry = (uint32_t)((uint64_t)x << (ZBITS - d) & ZMASK);
  }
  ztrim(r, bn, 0);
}
static Mpz *zdiv(const Mpz *a, const Mpz *b, int remainder) {
  if (!b->size) pys_fail(remainder ? "ZeroDivisionError: integer modulo by zero" : "ZeroDivisionError: integer division or modulo by zero");
  I an = zn(a), bn = zn(b);
  /* q and r are private until returned; q keeps a spare digit for zmuladd below */
  Mpz *q = zalloc(an + 1), *r;
  if (zcmpmag(a, b) < 0) { r = zcopy(a, 0); r->size = an; }
  else if (bn == 1) {   /* one-digit divisor, as CPython's divrem1 */
    uint64_t rem = 0; uint32_t n = b->d[0];
    for (I i = an; i; i--) { uint64_t x = rem << ZBITS | a->d[i - 1]; q->d[i - 1] = (uint32_t)(x / n); rem = x % n; }
    ztrim(q, an, 0); r = pys_mpz_from_int((I)rem);   /* fresh unless the shared zero */
  } else { r = zalloc(bn); zdivrem(a, b, q, r); }
  int negative = (a->size < 0) != (b->size < 0);
  if (negative && r->size) {
    zmuladd(q, 1, 1); r = zsubmag(b, r);
  }
  if (negative) q->size = -q->size;
  if (b->size < 0 && r->size) r->size = -r->size;
  return remainder ? r : q;
}
/* Read an infinite two's-complement operand one limb at a time. One extra limb
   makes its sign extension explicit; convert the finite result back to magnitude. */
static Mpz *zbitwise(const Mpz *a, const Mpz *b, I op) {
  I an = zn(a), bn = zn(b), n = (an > bn ? an : bn) + 1;
  Mpz *r = zalloc(n); uint64_t ac = a->size < 0, bc = b->size < 0;
  for (I i = 0; i < n; i++) {
    uint64_t av = i < an ? a->d[i] : 0, bv = i < bn ? b->d[i] : 0;
    if (a->size < 0) { av = (av ^ ZMASK) + ac; ac = av >> ZBITS; av &= ZMASK; }
    if (b->size < 0) { bv = (bv ^ ZMASK) + bc; bc = bv >> ZBITS; bv &= ZMASK; }
    r->d[i] = op == 5 ? av & bv : op == 6 ? av | bv : av ^ bv;
  }
  int negative = (r->d[n - 1] & (UINT32_C(1) << (ZBITS - 1))) != 0;
  if (negative) {
    uint64_t carry = 1;
    for (I i = 0; i < n; i++) { carry += r->d[i] ^ ZMASK; r->d[i] = carry & ZMASK; carry >>= ZBITS; }
  }
  ztrim(r, n, negative); return r;
}
void *pys_mpz_binop(void *ap, void *bp, I op) {
  Mpz *a = ap, *b = bp;
  if (op == 0 || op == 1) return zadd(a, b, op == 1);
  if (op == 2) return zmul(a, b);
  if (op == 3 || op == 4) return zdiv(a, b, op == 4);
  if (op >= 5 && op <= 7) return zbitwise(a, b, op);
  pys_fail("ValueError: invalid mpz operation");
}
void *pys_mpz_unary(void *ap, I op) {
  Mpz *a = ap, *r;
  if (op == 0 || op == 1) { r = zcopy(a, 0); r->size = op ? zn(r) : -r->size; return r; }
  if (op != 2) pys_fail("ValueError: invalid mpz operation");
  r = zcopy(a, 1); r->size = zn(r);
  if (a->size < 0) {
    I i = 0;
    while (!r->d[i]) { r->d[i++] = ZMASK; }
    r->d[i]--; ztrim(r, r->size, 0);
  } else { zmuladd(r, 1, 1); r->size = -r->size; }
  return r;
}
I pys_mpz_bit_length(void *ap) {
  Mpz *a = ap; I n = zn(a), bits = 0;
  if (!n) return 0;
  uint32_t v = a->d[n - 1]; while (v) { v >>= 1; bits++; }
  return (n - 1) * ZBITS + bits;
}
void *pys_mpz_shift(void *ap, I count, I right) {
  Mpz *a = ap; I n = zn(a);
  if (count < 0) pys_fail("ValueError: negative shift count");
  if (!count || !n) return a;
  I whole = count / ZBITS; unsigned part = count % ZBITS;
  if (right) {
    if (whole >= n) return pys_mpz_from_int(a->size < 0 ? -1 : 0);
    Mpz *r = zalloc(n - whole + 1); int lost = 0;
    for (I i = 0; i < whole; i++) if (a->d[i]) lost = 1;
    if (part && (a->d[whole] & ((UINT32_C(1) << part) - 1))) lost = 1;
    for (I i = whole; i < n; i++) {
      uint64_t v = a->d[i]; if (i + 1 < n) v |= (uint64_t)a->d[i + 1] << ZBITS;
      r->d[i - whole] = (v >> part) & ZMASK;
    }
    ztrim(r, n - whole, 0);
    if (a->size < 0) { if (lost) zmuladd(r, 1, 1); r->size = -r->size; }
    return r;
  }
  if (whole > (INT64_MAX - 64) / ZBITS - n - 1) pys_fail("OverflowError: mpz is too large");
  Mpz *r = zalloc(n + whole + 1); uint64_t carry = 0;
  for (I i = 0; i < n; i++) {
    uint64_t v = ((uint64_t)a->d[i] << part) | carry; r->d[i + whole] = v & ZMASK; carry = v >> ZBITS;
  }
  r->d[n + whole] = carry; ztrim(r, n + whole + 1, a->size < 0); return r;
}
void *pys_mpz_pow(void *ap, I exponent) {
  if (exponent < 0) pys_fail("ValueError: mpz exponent must be nonnegative");
  Mpz *a = ap, *r = pys_mpz_from_int(1);
  while (exponent) {
    if (exponent & 1) r = zmul(r, a);
    exponent >>= 1; if (exponent) a = zmul(a, a);
  }
  return r;
}
I pys_mpz_to_int(void *ap) {
  Mpz *a = ap; I n = zn(a);
  uint64_t u = 0, limit = a->size < 0 ? UINT64_C(1) << 63 : INT64_MAX;
  for (I i = n; i; i--) {
    if (u > (limit - a->d[i - 1]) / ZBASE) pys_fail("OverflowError: mpz does not fit in signed 64-bit int");
    u = (u << ZBITS) | a->d[i - 1];
  }
  if (a->size < 0) return u == (UINT64_C(1) << 63) ? INT64_MIN : -(I)u;
  return (I)u;
}
I pys_mpz_hash(void *ap) {
  /* CPython's 64-bit integer hash: magnitude modulo 2^61-1, then sign. */
  Mpz *a = ap; uint64_t h = 0, prime = (UINT64_C(1) << 61) - 1;
  for (I i = zn(a); i; i--) {
    h = ((h << ZBITS) & prime) | (h >> (61 - ZBITS));
    h += a->d[i - 1]; if (h >= prime) h -= prime;
  }
  I r = a->size < 0 ? -(I)h : (I)h; return r == -1 ? -2 : r;
}
#define DIGITS_LIMIT "ValueError: Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit"
/* a's decimal text, or NULL where it has more digits than CPython's default limit, which
   pys_mpz_str raises for (and runtime.c's repr of a list of ints: digits_deep) */
static Str *mpz_digits(Mpz *a) {
  I n = zn(a);
  if (!n) return cstr("0");
  /* Decimal conversion deliberately follows CPython's default 4300-digit limit.
     A value with >= 14286 bits necessarily exceeds it, avoiding huge scratch. */
  if (pys_mpz_bit_length(a) > 14285) return NULL;
  /* Base-10^9 digits, least significant first, in one pass per digit from the most
     significant (Knuth 4.4 Method 1b, as CPython's long_to_decimal_string_internal):
     only a quotient carries along a pass, so each step waits on one division. There are
     at most n + n/99 + 1 of them, CPython's bound for 30-bit digits. */
  uint32_t *dec = pys_alloc_atomic((n + n / 99 + 1) * sizeof(uint32_t)); I m = 0;
  for (I i = n; i; i--) {
    uint32_t hi = a->d[i - 1];
    for (I j = 0; j < m; j++) {
      uint64_t z = (uint64_t)dec[j] << ZBITS | hi;
      hi = (uint32_t)(z / 1000000000); dec[j] = (uint32_t)(z - (uint64_t)hi * 1000000000);
    }
    while (hi) { dec[m++] = hi % 1000000000; hi /= 1000000000; }
  }
  int negative = a->size < 0; I out = negative + 9 * (m - 1);
  for (uint32_t top = dec[m - 1]; top; top /= 10) out++;
  if (out - negative > 4300) return NULL;
  Str *s = pys_alloc_atomic(sizeof(Str) + out + 1); I k = out;
  for (I j = 0; j < m; j++)   /* nine digits each, zero-padded, except the most significant */
    for (uint32_t v = dec[j], d = 0; d < 9 && (j + 1 < m || v); d++) { s->s[--k] = '0' + v % 10; v /= 10; }
  if (negative) s->s[--k] = '-';
  s->len = out; s->chars1 = out + 1; return s;
}
Str *pys_mpz_str(void *ap) {
  Str *s = mpz_digits(ap);
  if (!s) pys_fail(DIGITS_LIMIT);
  return s;
}

#undef ZBITS
#undef ZBASE
#undef ZMASK
