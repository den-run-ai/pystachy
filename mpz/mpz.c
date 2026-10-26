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
   MicroPython mpn schoolbook multiply and normalized division adapted to indexed
   loops. This file is included by runtime.c after its numeric parsing helpers.
   No MPZ object contains a pointer; class fields and containers root the handle.
   Only fresh, unpublished result/scratch objects are mutated.
   Parsing and decimal formatting follow CPython 3.13.16's Objects/longobject.c
   (Python Software Foundation License Version 2; see THIRD_PARTY_NOTICES and
   mpz/README.md): linear power-of-two bases, digit groups in other bases, and
   Knuth's single-pass conversion to base 10^9. */

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
/* Magnitude addition/subtraction. Subtraction requires |a| >= |b|. */
static Mpz *zaddmag(const Mpz *a, const Mpz *b, int subtract) {
  I an = zn(a), bn = zn(b), n = an > bn ? an : bn; Mpz *r = zalloc(n + 1);
  uint64_t carry = 0;
  for (I i = 0; i < n; i++) {
    uint64_t x = i < an ? a->d[i] : 0, y = i < bn ? b->d[i] : 0;
    if (subtract) { uint64_t d = x - y - carry; carry = x < y + carry; r->d[i] = d & ZMASK; }
    else { uint64_t d = x + y + carry; carry = d >> ZBITS; r->d[i] = d & ZMASK; }
  }
  if (!subtract && carry) r->d[n++] = carry;
  ztrim(r, n, 0); return r;
}
static Mpz *zadd(const Mpz *a, const Mpz *b, int subtract) {
  int na = a->size < 0, nb = (b->size < 0) ^ subtract, c = zcmpmag(a, b);
  Mpz *r;
  if (na == nb) r = zaddmag(a, b, 0);
  else if (c >= 0) r = zaddmag(a, b, 1);
  else { r = zaddmag(b, a, 1); na = nb; }
  if (na) r->size = -r->size;
  return r;
}
/* Schoolbook multiplication adapted from MicroPython mpn_mul. A 30-bit digit
   product plus one result digit and carry fits uint64_t without wrapping. */
static Mpz *zmul(const Mpz *a, const Mpz *b) {
  I an = zn(a), bn = zn(b);
  if (!an || !bn) return (Mpz *)&mpz_zero;
  Mpz *r = zalloc(an + bn);
  for (I j = 0; j < bn; j++) {
    uint64_t carry = 0;
    for (I i = 0; i < an; i++) {
      carry += (uint64_t)a->d[i] * b->d[j] + r->d[i + j];
      r->d[i + j] = carry & ZMASK; carry >>= ZBITS;
    }
    r->d[an + j] = carry;
  }
  ztrim(r, an + bn, (a->size < 0) != (b->size < 0)); return r;
}
/* Normalized long division, adapted from MicroPython mpn_div. The divisor is
   normalized on demand. Indexed loops never form pointers before an array. */
static void zdivmag(Mpz *r, const Mpz *b, Mpz *q) {
  I rn = zn(r), bn = zn(b); int c = zcmpmag(r, b);
  if (c < 0) { q->size = 0; return; }
  if (!c) { r->size = 0; q->size = 1; q->d[0] = 1; return; }
  unsigned shift = 0; uint32_t top = b->d[bn - 1];
  while (!(top & (UINT32_C(1) << (ZBITS - 1)))) { top <<= 1; shift++; }
  uint64_t carry = 0;
  for (I i = 0; i <= rn; i++) {
    uint64_t v = ((uint64_t)r->d[i] << shift) | carry;
    r->d[i] = v & ZMASK; carry = v >> ZBITS;
  }
  rn++;
  uint64_t lead = (uint64_t)b->d[bn - 1] << shift;
  if (bn >= 2) lead |= (uint64_t)b->d[bn - 2] >> (ZBITS - shift);
  I qn = rn - bn;
  for (I k = qn; k; k--) {
    I high = k + bn - 1;
    uint64_t quotient = (((uint64_t)r->d[high] << ZBITS) | r->d[high - 1]) / lead;
    uint64_t norm = 0; int64_t borrow = 0;
    for (I j = 0; j < bn; j++) {
      norm = ((uint64_t)b->d[j] << shift) | (norm >> ZBITS);
      uint64_t product = quotient * (norm & ZMASK);
      int64_t low = (borrow & ZMASK) + r->d[k - 1 + j] - (product & ZMASK);
      r->d[k - 1 + j] = low & ZMASK;
      borrow = (borrow >> ZBITS) - (int64_t)(product >> ZBITS) + (low >> ZBITS);
    }
    borrow += r->d[high];
    while (borrow) {
      norm = 0; carry = 0;
      for (I j = 0; j < bn; j++) {
        norm = ((uint64_t)b->d[j] << shift) | (norm >> ZBITS);
        carry += r->d[k - 1 + j] + (norm & ZMASK);
        r->d[k - 1 + j] = carry & ZMASK; carry >>= ZBITS;
      }
      borrow += (int64_t)carry; quotient--;
    }
    q->d[k - 1] = quotient & ZMASK;
  }
  carry = 0;
  for (I i = bn; i; i--) {
    uint32_t digit = r->d[i - 1];
    r->d[i - 1] = ((digit >> shift) | carry) & ZMASK;
    carry = (uint64_t)digit << (ZBITS - shift);
  }
  ztrim(q, qn, 0); ztrim(r, bn, 0);
}
static Mpz *zdiv(const Mpz *a, const Mpz *b, int remainder) {
  if (!b->size) pys_fail(remainder ? "ZeroDivisionError: integer modulo by zero" : "ZeroDivisionError: integer division or modulo by zero");
  Mpz *q = zalloc(zn(a) + 1), *r = zcopy(a, 1);
  r->size = zn(r); zdivmag(r, b, q);
  int negative = (a->size < 0) != (b->size < 0);
  if (negative && r->size) {
    zmuladd(q, 1, 1); r = zaddmag(b, r, 1);
  }
  if (negative) q->size = -q->size;
  if (b->size < 0) r->size = -r->size;
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
Str *pys_mpz_str(void *ap) {
  Mpz *a = ap; I n = zn(a);
  if (!n) return cstr("0");
  /* Decimal conversion deliberately follows CPython's default 4300-digit limit.
     A value with >= 14286 bits necessarily exceeds it, avoiding huge scratch. */
  if (pys_mpz_bit_length(a) > 14285) pys_fail("ValueError: Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit");
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
  if (out - negative > 4300) pys_fail("ValueError: Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit");
  Str *s = pys_alloc_atomic(sizeof(Str) + out + 1); I k = out;
  for (I j = 0; j < m; j++)   /* nine digits each, zero-padded, except the most significant */
    for (uint32_t v = dec[j], d = 0; d < 9 && (j + 1 < m || v); d++) { s->s[--k] = '0' + v % 10; v /= 10; }
  if (negative) s->s[--k] = '-';
  s->len = out; s->chars1 = out + 1; return s;
}

#undef ZBITS
#undef ZBASE
#undef ZMASK
