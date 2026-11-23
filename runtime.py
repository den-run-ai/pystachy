"""Pystachy runtime, the part written in the subset itself.

`pystachy rt runtime.py` compiles it like a program, but each `pys_*` function is defined under
its C name with runtime.c's types (bools cross as int), and the driver links it to runtime.c's
bitcode into the cached runtime (build/runtime-py-<L>-<K>.bc and its .o, named by a hash of
what they are built from, this file's bytes among it). runtime.c keeps a
prototype of each function moved here. Programs call these functions exactly as they call
runtime.c's, so their IR does not change (but for an invoke inside a try, where RUNTIME says a
function moved here can raise and runtime.c's could not).

The rules for this file: functions, imports and docstrings only (nothing runs module code); no
classes; no bools in a pys_* signature; and a function may not use the operation it implements
(math.gcd() inside pys_m_gcd would call itself). CPython can run it too, where its strs hold
bytes (as pystachy.py reads source files, as Latin-1).
"""
import math

import _rt


# ---------- scalar math (native ABI, no heap allocations) ----------
# Preserve the C helpers' literal constants and operation ordering.


def pys_m_degrees(x: float) -> float:
    return x * (180.0 / 3.141592653589793)


def pys_m_radians(x: float) -> float:
    return x * (3.141592653589793 / 180.0)


# Derived from CPython's Modules/mathmodule.c, math_isclose_impl.
# Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved.
# Used under the PSF License Agreement; see THIRD_PARTY_NOTICES.
def pys_m_isclose(a: float, b: float, rel_tol: float, abs_tol: float) -> int:
    # CPython's math.isclose order: reject negative tolerances, including -inf.
    # NaNs are intentionally not rejected by that comparison.
    if rel_tol < 0.0 or abs_tol < 0.0:
        raise ValueError("tolerances must be non-negative")
    if a == b:
        return 1  # same-signed infinities compare equal
    if math.isinf(a) or math.isinf(b):
        return 0
    diff = abs(b - a)
    # Separate exits preserve this short circuit through runtime preoptimization.
    if diff <= abs(rel_tol * b):
        return 1
    if diff <= abs(rel_tol * a):
        return 1
    return 1 if diff <= abs_tol else 0


# ---------- checked integer arithmetic and unsigned range arithmetic ----------


def pys_floordiv(a: int, b: int) -> int:
    # Handle -1 before computing a remainder, so the two instructions below can share one
    # hardware division. sdiv(a, -1) is a checked negation, including MIN's overflow.
    if b == -1:
        return _rt.sdiv(a, -1)
    q = _rt.sdiv(a, b)
    # Signed division truncates toward zero. A negative, non-integral quotient is one lower.
    if _rt.srem(a, b) != 0 and (a ^ b) < 0:
        return _rt.wrap_sub(q, 1)
    return q


def pys_mod(a: int, b: int) -> int:
    if b == -1:
        return 0
    r = _rt.srem(a, b)
    # The machine remainder has the dividend's sign; Python's has the divisor's.
    if r == 0 or (r ^ b) >= 0:
        return r
    return _rt.wrap_add(r, b)


def pys_int_bit_length(a: int) -> int:
    # Count bits of the magnitude, including 2**63 for the most negative int.
    x = _rt.wrap_sub(0, a) if a < 0 else a
    # Setting bit 0 preserves the highest set bit and gives zero an index of 0.
    highest = _rt.wrap_sub(63, _rt.ctlz(x | 1))
    return _rt.wrap_add(highest, int(a != 0))


def pys_int_bit_count(a: int) -> int:
    x = _rt.wrap_sub(0, a) if a < 0 else a
    return _rt.ctpop(x)


def pys_pow(a: int, b: int) -> int:
    if b < 0:
        if a == 0:
            raise ZeroDivisionError("0.0 cannot be raised to a negative power")
        raise ValueError("negative exponent for int ** int")
    r = 1
    x = a
    if a == 0 or a == 1:
        return a if b != 0 else 1
    if a == -1:
        return -1 if b & 1 else 1
    while True:  # |a| >= 2: either the result fits or checked multiplication raises
        if b & 1:
            r *= x
        b = _rt.lshr(b, 1)
        if b == 0:
            return r
        x *= x


def pys_idiv(a: int, b: int) -> float:
    if b == 0:
        raise ZeroDivisionError("division by zero")
    # Bias the exactly representable interval [-2**53, 2**53) to [0, 2**54).
    if _rt.lshr(_rt.wrap_add(a, 9007199254740992) | _rt.wrap_add(b, 9007199254740992), 54) == 0:
        return _rt.fdiv(float(a), float(b))
    x = _rt.wrap_sub(0, a) if a < 0 else a
    y = _rt.wrap_sub(0, b) if b < 0 else b
    # For a nonzero dividend, keep at least 55 quotient bits: 53 significand bits plus round and sticky.
    shift = max(0, 55 + _rt.ctlz(x) - _rt.ctlz(y))
    part = _rt.shl(x, shift)  # _rt.shl shifts a word by shift modulo 64
    if shift < 64:
        # Two right shifts give zero at shift == 0, where a shift by 64 would wrap.
        hi = _rt.lshr(_rt.lshr(x, 1), 63 - shift)
        lo = part
    else:
        # The first 64 shifts move x into the high word; part applies the remaining shifts.
        hi = part
        lo = 0
    q = _rt.udiv_wide(hi, lo, y)
    # The remainder is smaller than 2**64, so its low word alone tells us whether it is nonzero.
    if _rt.wrap_mul(q, y) != lo:
        q |= 1
    # Only a quotient of 2**63 has its sign bit set; its signed float conversion is exactly -2**63.
    # Give the power-of-two scale the result sign, including for a zero dividend.
    scale_bits = _rt.shl(1023 - shift, 52) | ((a ^ b) & (-9223372036854775807 - 1))
    return abs(float(q)) * _rt.bits_float(scale_bits)


def mulmod(a: int, b: int, n: int) -> int:
    # a * b % n of 64-bit patterns as unsigned ints: the product has 128 bits
    return _rt.urem_wide(_rt.mul_hi(a, b), _rt.wrap_mul(a, b), n)


def pys_powmod(a: int, b: int, m: int) -> int:
    # pow(a, b, m) as CPython's long_pow: the result has the sign of m. The modulus is taken as
    # an unsigned int, which holds the 2**63 of -2**63, and so are the values below it
    if m == 0:
        raise ValueError("pow() 3rd argument cannot be 0")
    n = _rt.wrap_sub(0, m) if m < 0 else m
    if n == 1:
        return 0
    x = _rt.urem(a, n)
    if a < 0:
        x = _rt.urem(_rt.wrap_sub(0, a), n)
        if x != 0:
            x = _rt.wrap_sub(n, x)
    e = b
    if b < 0:
        # a negative exponent: the power of x's inverse modulo n (long_invmod), by Euclid's
        # algorithm. s and t are the coefficients of x in p and q, below n in magnitude; the
        # last t alone, which nothing reads, may be n itself and wrap
        p = x
        q = n
        s = 1
        t = 0
        while q != 0:
            d = _rt.udiv(p, q)
            u = _rt.wrap_sub(p, _rt.wrap_mul(d, q))
            w = _rt.wrap_sub(s, _rt.wrap_mul(d, t))
            p = q
            q = u
            s = t
            t = w
        if p != 1:
            raise ValueError("base is not invertible for the given modulus")
        x = _rt.wrap_add(s, n) if s < 0 else s
        e = _rt.wrap_sub(0, b)
    r = 1
    while e != 0:
        if e & 1:
            r = mulmod(r, x, n)
        x = mulmod(x, x, n)
        e = _rt.lshr(e, 1)
    return _rt.wrap_sub(r, n) if m < 0 and r != 0 else r


def pys_shl(a: int, b: int) -> int:
    if b < 0:
        raise ValueError("negative shift count")
    if b < 64:
        shifted = _rt.shl(a, b)
        # Shifting back restores a exactly when no significant bit was lost.
        if _rt.ashr(shifted, b) == a:
            return shifted
    elif a == 0:
        return 0
    raise OverflowError("integer result does not fit in 64 bits")


def pys_shr(a: int, b: int) -> int:
    if b < 0:
        raise ValueError("negative shift count")
    return _rt.ashr(a, b if b < 63 else 63)


def pys_round_int(x: int, n: int) -> int:
    # round(x, n) of an int: x, or for n < 0 the nearest multiple of m = 10**-n, ties to the even
    # multiple. 10**19 is past 2**63 and 10**20 past 2**64: there x rounds to 0, or to 10**19 or
    # its negative, which no 64-bit int holds
    if n >= 0:
        return x
    if n < -19:
        return 0
    if n == -19:
        if x > 5000000000000000000 or x < -5000000000000000000:
            raise OverflowError("integer result does not fit in 64 bits")
        return 0
    m = 1
    for _ in range(-n):
        m *= 10
    q = x // m
    r = x % m  # x = q * m + r, 0 <= r < m (q * m itself may be below -2**63)
    if 2 * r > m or (2 * r == m and q & 1 != 0):
        q += 1
    return q * m


def pys_range_len(a: int, b: int, s: int) -> int:
    if s == 0:
        raise ValueError("range() arg 3 must not be zero")
    if s > 0:
        if a >= b:
            return 0
        d = _rt.wrap_sub(b, a)
        st = s
    else:
        if a <= b:
            return 0
        d = _rt.wrap_sub(a, b)
        st = _rt.wrap_sub(0, s)
    # Both the distance and count may exceed INT64_MAX. Keep their unsigned
    # 64-bit patterns; callers, including iterators, already use that ABI.
    return _rt.wrap_add(_rt.udiv(_rt.wrap_sub(d, 1), st), 1)


def pys_range_has(x: int, a: int, b: int, s: int) -> int:
    if s == 0:
        raise ValueError("range() arg 3 must not be zero")
    if s > 0:
        if x < a or x >= b:
            return 0
        d = _rt.wrap_sub(x, a)
        st = s
    else:
        if x <= b or x > a:
            return 0
        d = _rt.wrap_sub(a, x)
        st = _rt.wrap_sub(0, s)
    return 1 if _rt.urem(d, st) == 0 else 0


# ---------- the math module's integer functions ----------
# The subset's arithmetic is checked, so an int result that does not fit in 64 bits raises
# CPython's OverflowError where runtime.c had to test for it by hand. There are no unsigned or
# 128-bit ints: gcd divides unsigned 64-bit patterns with _rt.urem (|-2**63| fits in them), and
# comb asks _rt.mul_ovf before it multiplies.


def pys_m_gcd(a: int, b: int) -> int:
    x = _rt.wrap_sub(0, a) if a < 0 else a  # |a| as an unsigned 64-bit pattern
    y = _rt.wrap_sub(0, b) if b < 0 else b
    while y != 0:
        t = _rt.urem(x, y)
        x = y
        y = t
    if x < 0:
        raise OverflowError("integer result does not fit in 64 bits")  # gcd(-2**63, 0) = 2**63
    return x


def pys_m_lcm(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    r = a // pys_m_gcd(a, b) * b
    return -r if r < 0 else r


def pys_m_isqrt(n: int) -> int:
    if n < 0:
        raise ValueError("isqrt() argument must be nonnegative")
    # the float root is within one of the answer; squares fix it up, which cost less than quotients
    # (mul_ovf: a square past the largest int is past n)
    r = int(math.sqrt(float(n)))
    while _rt.mul_ovf(r, r) or r * r > n:
        r -= 1
    while not _rt.mul_ovf(r + 1, r + 1) and (r + 1) * (r + 1) <= n:
        r += 1
    return r


def pys_m_factorial(n: int) -> int:
    if n < 0:
        raise ValueError("factorial() not defined for negative values")
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


def nonneg(n: int, k: int) -> None:
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    if k < 0:
        raise ValueError("k must be a non-negative integer")


def pys_m_comb(n: int, k: int) -> int:
    nonneg(n, k)
    if k > n:
        return 0
    if k > n - k:
        k = n - k
    # r = C(n - k + i, i) after step i, which never exceeds the result. i divides r * m, so where
    # that product overflows, r * m // i is r // i * m + r % i * m // i, and no step overflows
    # unless the result does (r % i * m < i * m, and where i * m reaches 2**63 so does C(n, k)).
    # All are positive: unsigned division, which is much faster than floor division
    r = 1
    for i in range(1, k + 1):
        m = n - k + i
        if _rt.mul_ovf(r, m):
            r = _rt.udiv(r, i) * m + _rt.udiv(_rt.urem(r, i) * m, i)
        else:
            r = _rt.udiv(r * m, i)
    return r


def pys_m_perm(n: int, k: int) -> int:
    nonneg(n, k)
    if k > n:
        return 0
    r = 1
    for i in range(k):
        r *= n - i
    return r


# ---------- any, all and the sums of ints ----------
# A list of ints or bools holds each item in an 8-byte slot. From an int start, sum() adds them
# with the checked arithmetic; from a float start, each as a float, without compensation. (For
# the sums and the product of a list that may hold an int past 64 bits, the compiler first calls
# pys_list_narrow, which refuses one: NARROWED.)


def pys_any(xs: list[int]) -> int:
    for x in xs:
        if x != 0:
            return 1
    return 0


def pys_all(xs: list[int]) -> int:
    for x in xs:
        if x == 0:
            return 0
    return 1


def pys_sum_int(xs: list[int], s: int) -> int:
    for x in xs:
        s += x
    return s


def pys_sum_int_float(xs: list[int], s: float) -> float:
    for x in xs:
        s += float(x)
    return s


# ---------- sum of floats ----------
# CPython's compensated (Neumaier) sum, preserving the C implementation's
# arithmetic order. An integer start adds its first float without compensation.


def pys_sum_float(xs: list[float], s: float) -> float:
    c = 0.0
    for x in xs:
        t = s + x
        if abs(s) >= abs(x):
            c += (s - t) + x
        else:
            c += (x - t) + s
        s = t
    return s + c if c != 0.0 and math.isfinite(c) else s


def pys_sum_float_int(xs: list[float], start: int) -> float:
    if len(xs) == 0:
        return float(start)
    s = float(start) + xs[0]
    c = 0.0
    for i in range(1, len(xs)):
        x = xs[i]
        t = s + x
        if abs(s) >= abs(x):
            c += (s - t) + x
        else:
            c += (x - t) + s
        s = t
    return s + c if c != 0.0 and math.isfinite(c) else s


# ---------- math.fsum and math.prod ----------
# fsum is CPython's math_fsum, Shewchuk's exact summation: the partials hold the sum so far
# exactly, as nonzero, nonoverlapping floats increasing in magnitude, and are rounded once at the
# end; infs and nans are summed apart. prod multiplies left to right, ints with the checked
# arithmetic. Where CPython makes a float of an int item (in fsum, and in a product with a
# float), the compiler passes the list through pys_m_floats.


def pys_m_fsum(xs: list[float]) -> float:
    p: list[float] = []  # the partials: p[:n]
    n = 0
    special = 0.0  # the sum of the infs and nans
    infs = 0.0  # of the infs: a nan if both signs occur
    for v in xs:
        x = v
        i = 0
        for j in range(n):
            y = p[j]
            if abs(x) < abs(y):
                t = x
                x = y
                y = t
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                p[i] = lo
                i += 1
            x = hi
        n = i
        if x != 0.0:
            if not math.isfinite(x):
                # an inf or a nan, or a sum past the largest float
                if math.isfinite(v):
                    raise OverflowError("intermediate overflow in fsum")
                if math.isinf(v):
                    infs += v
                special += v
                n = 0
            else:
                if n == len(p):
                    p.append(x)
                else:
                    p[n] = x
                n += 1
    if special != 0.0:
        if math.isnan(infs):
            raise ValueError("-inf + inf in fsum")
        return special
    hi = 0.0
    lo = 0.0
    if n > 0:
        # the partials from the largest down, while their sum is exact
        n -= 1
        hi = p[n]
        while n > 0:
            x = hi
            n -= 1
            y = p[n]
            hi = x + y
            lo = y - (hi - x)
            if lo != 0.0:
                break
        # half-even rounding across the partials: the rest of them may break a tie
        if n > 0 and ((lo < 0.0 and p[n - 1] < 0.0) or (lo > 0.0 and p[n - 1] > 0.0)):
            y = lo * 2.0
            x = hi + y
            if y == x - hi:
                hi = x
    return hi


def pys_m_prod_int(xs: list[int], start: int) -> int:
    r = start
    for x in xs:
        r *= x
    return r


def pys_m_prod_float(xs: list[float], start: float) -> float:
    r = start
    for x in xs:
        r *= x
    return r


def pys_m_floats(xs: list[int]) -> list[float]:
    return [float(x) for x in xs]


# ---------- math.hypot, math.dist and math.fma ----------
# hypot and dist are CPython's vector_norm, not libm's hypot, so that the last bit agrees: the
# coordinates are scaled by a power of two so that the largest is in [0.5, 1), which loses
# nothing; each square is exact as a float and what fma() shows the float left out; the squares
# are summed from 1.0, which keeps every sum exact but for what the two frac sums gather; and the
# square root gets one correction from the difference of its square. It never raises: the result
# is inf where a coordinate is, else nan where one is. The largest coordinate is found in a
# first pass over the list, so that no copy of the coordinates is needed.
# Derived from CPython's Modules/mathmodule.c, vector_norm.
# Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved.
# Used under the PSF License Agreement; see THIRD_PARTY_NOTICES.


def norm_tiny(max: float) -> bool:
    # max > 0 is below 2**-1024: frexp()'s exponent e of it is below -1023, and no float is
    # 2**-e. Such coordinates are first divided by 2**-1022, the smallest normal float, exactly
    return _rt.float_bits(max) < 1125899906842624  # (2**50)


def norm_scale(max: float) -> float:
    # ldexp(1.0, -e) for the e of frexp(max), 2**-1024 <= max < 2**1024: max * scale is in [0.5, 1)
    b = _rt.float_bits(max)
    be = _rt.lshr(b, 52)  # (the exponent's bits: max > 0)
    if be >= 2045:
        return _rt.bits_float(_rt.shl(1, 2096 - be))  # 2**-1023 and 2**-1024, which are subnormal
    if be == 0:
        return _rt.bits_float(_rt.shl(2046 if b < 2251799813685248 else 2045, 52))  # (max is; 2**51)
    return _rt.bits_float(_rt.shl(2045 - be, 52))


def norm_done(csum: float, frac1: float, frac2: float, scale: float) -> float:
    h = _rt.sqrt(csum - 1.0 + (frac1 + frac2))
    hi = -h * h
    frac1 += _rt.fma(-h, h, -hi)
    t = csum + hi
    frac2 += (csum - t) + hi
    x = t - 1.0 + (frac1 + frac2)
    h += _rt.fdiv(x, 2.0 * h)  # (h and scale are above zero: nothing to check)
    return _rt.fdiv(h, scale)


def norm_small(p: list[float], q: list[float], paired: bool, max: float) -> float:
    # the norm of p, or of p - q, where the largest coordinate is below 2**-1024 (norm_tiny): each
    # is divided by 2**-1022 first, exactly, and the result multiplied by it. It has a loop of
    # its own, so that the others do no more for each coordinate than scale it
    scale = norm_scale(max / 2.2250738585072014e-308)
    csum = 1.0
    frac1 = 0.0
    frac2 = 0.0
    for i in range(len(p)):
        c = p[i] - q[i] if paired else p[i]
        v = abs(c) / 2.2250738585072014e-308 * scale
        hi = v * v
        frac1 += _rt.fma(v, v, -hi)
        t = csum + hi
        frac2 += (csum - t) + hi
        csum = t
    return 2.2250738585072014e-308 * norm_done(csum, frac1, frac2, scale)


def norm_pair(a: float, b: float, max: float) -> float:
    # the norm of two coordinates, a and b >= 0, whose largest is max >= 2**-1024
    scale = norm_scale(max)
    csum = 1.0
    frac1 = 0.0
    frac2 = 0.0
    v = a * scale
    hi = v * v
    frac1 += _rt.fma(v, v, -hi)
    t = csum + hi
    frac2 += (csum - t) + hi
    csum = t
    v = b * scale
    hi = v * v
    frac1 += _rt.fma(v, v, -hi)
    t = csum + hi
    frac2 += (csum - t) + hi
    return norm_done(t, frac1, frac2, scale)


def pys_m_hypot(x: float, y: float) -> float:
    a = abs(x)
    b = abs(y)
    max = 0.0
    if a > max:
        max = a
    if b > max:  # (a nan is never the max)
        max = b
    if math.isinf(max):
        return max
    if math.isnan(x) or math.isnan(y):
        return _rt.bits_float(9221120237041090560)  # (a quiet nan, 0x7ff8 << 48)
    if max == 0.0:
        return max
    if norm_tiny(max):
        d = 2.2250738585072014e-308
        return d * norm_pair(a / d, b / d, max / d)
    return norm_pair(a, b, max)


def pys_m_hypot_list(p: list[float]) -> float:
    max = 0.0
    nan = False
    for c in p:
        v = abs(c)
        if v != v:
            nan = True
        if v > max:
            max = v
    if math.isinf(max):
        return max
    if nan:
        return _rt.bits_float(9221120237041090560)
    if max == 0.0 or len(p) <= 1:
        return max
    if norm_tiny(max):
        return norm_small(p, p, False, max)
    scale = norm_scale(max)
    csum = 1.0
    frac1 = 0.0
    frac2 = 0.0
    for c in p:
        v = abs(c) * scale
        hi = v * v
        frac1 += _rt.fma(v, v, -hi)
        t = csum + hi
        frac2 += (csum - t) + hi
        csum = t
    return norm_done(csum, frac1, frac2, scale)


def pys_m_dist(p: list[float], q: list[float]) -> float:
    n = len(p)
    if n != len(q):
        raise ValueError("both points must have the same number of dimensions")
    max = 0.0
    nan = False
    for i in range(n):
        v = abs(p[i] - q[i])
        if v != v:
            nan = True
        if v > max:
            max = v
    if math.isinf(max):
        return max
    if nan:
        return _rt.bits_float(9221120237041090560)
    if max == 0.0 or n <= 1:
        return max
    if norm_tiny(max):
        return norm_small(p, q, True, max)
    scale = norm_scale(max)
    csum = 1.0
    frac1 = 0.0
    frac2 = 0.0
    for i in range(n):
        v = abs(p[i] - q[i]) * scale
        hi = v * v
        frac1 += _rt.fma(v, v, -hi)
        t = csum + hi
        frac2 += (csum - t) + hi
        csum = t
    return norm_done(csum, frac1, frac2, scale)


def pys_m_fma(x: float, y: float, z: float) -> float:
    # x * y + z, rounded once
    r = _rt.fma(x, y, z)
    if math.isnan(r) and not math.isnan(x) and not math.isnan(y) and not math.isnan(z):
        raise ValueError("invalid operation in fma")
    if math.isinf(r) and math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
        raise OverflowError("overflow in fma")
    return r


# ---------- str methods ----------
# A str is a length and its bytes (UTF-8). _rt.byte reads one without making a 1-char str, and
# _rt.str_new/str_put/copy/str_done build a new str in place, where runtime.c used memcpy, memmem
# and its Buf. Case mapping, the is*() tests and whitespace know only ASCII, as in runtime.c.


def adj_start(st: int, n: int) -> int:
    # CPython's ADJUST_INDICES, for s[st:en] in the search methods (adj_end: the end)
    if st < 0:
        st += n
        if st < 0:
            st = 0
    return st


def adj_end(en: int, n: int) -> int:
    if en > n:
        return n
    if en < 0:
        en += n
        if en < 0:
            en = 0
    return en


def match(h: str, i: int, n: str) -> bool:
    # whether n occurs in h at i, which leaves room for it, given that its first byte does: byte by
    # byte while it is short, else memcmp. (A wrapping add, as byte() checks the index anyway: match
    # and scan stay small enough for LLVM to inline into both search loops.)
    m = len(n)
    if m > 8:
        return _rt.same(h, i, n, 0, m)
    for j in range(1, m):
        if _rt.byte(h, _rt.wrap_add(i, j)) != _rt.byte(n, j):
            return False
    return True


def scan(s: str, c: int, i: int, n: int) -> int:
    # the first k in [i, n) where byte k of s is c, or -1: inline over 8 bytes (dense candidates),
    # then memchr (sparse ones). (Scans are range loops, which step with an nsw add where a while
    # loop's += is checked; byte()'s index check stays, as LLVM cannot tell that n <= len(s).)
    stop = _rt.wrap_add(i, 8)
    if stop > n:
        stop = n
    for k in range(i, stop):
        if _rt.byte(s, k) == c:
            return k
    return _rt.find_byte(s, c, stop, n) if stop < n else -1


def scan_ws(s: str, i: int, n: int, want: bool) -> int:
    # the first k in [i, n) where the character at k is whitespace (want) or not, or n. (The
    # index steps by a character's 1 to 4 bytes within s: wrapping adds, which cannot overflow,
    # here and in the other character loops below. Each loop tests an ASCII byte itself, and
    # calls wsat() and its kin, which LLVM does not inline, only for a non-ASCII one, as
    # runtime.c's ws() calls uws())
    k = i
    while k < n:
        c = _rt.byte(s, k)
        w = (1 if ws(c) else -1) if c < 128 else wsat(s, k, n)
        if (w > 0) == want:
            return k
        k = _rt.wrap_add(k, w) if w > 0 else _rt.wrap_sub(k, w)
    return n


def search(h: str, n: str, st: int, en: int) -> int:
    # the first i from st on where n occurs in h[:en], or -1. One byte goes to memchr, as runtime.c's
    # memmem sent it, not to seek()'s inline scan, whose exit mispredicts where the gaps between hits
    # vary (a loop of finds over the fields of CSV lines, lines, tags). (Here, not in seek(), which
    # in and count call for every search: a test there costs a short in 8% under the JIT)
    if len(n) == 1:
        return _rt.find_byte(h, _rt.byte(n, 0), st, en) if st < en else -1
    i = seek(h, n, st, en, st)
    return -2 - i if i < -1 else i


def seek(h: str, n: str, i: int, en: int, st: int) -> int:
    # search() from i, but -2 - k where memmem found k, in a loop over the occurrences that began
    # at st (again()). The next occurrence of n's first byte (scan), checked. A failed candidate
    # costs toll(len(n)) bytes of memmem's work; once failed candidates have cost more than the
    # bytes passed (and 64), memmem takes over for a stretch (stretch()), which is linear: the work
    # stays below about twice the text's length (Go's strings.Index makes a similar cutover). A
    # first byte as common as each "<" of HTML for "</span>" thus goes to memmem soon, as runtime.c
    # did, and a rare one stays with memchr, which is much faster there
    m = len(n)
    if m == 0:
        return i if i <= en else -1
    first = _rt.byte(n, 0)
    last = en - m  # the last place n can start
    paid = i - 64  # where the failed candidates' cost has reached: once past one, memmem
    while i <= last:
        k = scan(h, first, i, last + 1)
        if k < 0 or match(h, k, n):
            return k
        paid += toll(m)
        i = k + 1
        if paid > k:
            i = stretch(h, n, i, en, st)
            if i < 0:
                return i
            paid = i - 64
    return -1


def toll(m: int) -> int:
    # the cost of a failed candidate for a needle of m bytes, in bytes of memmem's work: memmem
    # skips about m - 1 bytes a step, and a candidate's scan, call and check cost about as much as
    # its steps over 12 times that where candidates are evenly spaced; at the irregular distances
    # of real text they mispredict, and 20 times that keeps the most text near memmem's time (a
    # sweep over real HTML and prose, docs/runtime-in-subset.md 2.10). It covers the up to m
    # comparisons too. (Wrapping, as m is a str's length, far below 2**59: LLVM computes toll()
    # and reach() at the start of every search, where overflow tests would cost each call.)
    return _rt.wrap_mul(_rt.wrap_sub(m, 1), 20)


def reach(i: int, st: int, m: int) -> int:
    # where a stretch of memmem from i ends, for a needle of m bytes: as far again as from st, but
    # at least 16 * m + 256 bytes on, as each stretch costs memmem a setup and seek() a candidate,
    # which can take m bytes each
    d = _rt.wrap_add(_rt.wrap_mul(m, 16), 256)
    return i + (i - st if i - st > d else d)


def stretch(h: str, n: str, i: int, en: int, st: int) -> int:
    # memmem from i to reach(): -2 - k where it found k, else -1 at the end, or where seek() counts
    # the candidates again. A loop over the occurrences goes on from each one memmem found, so a
    # dense text sees few such restarts, and a few tags before long paragraphs do not keep the
    # paragraphs from memchr
    m = len(n)
    stop = reach(i, st, m)
    if stop > en - m:
        k = _rt.find_sub(h, n, i, en)
        return -2 - k if k >= 0 else -1
    k = _rt.find_sub(h, n, i, stop + m - 1)
    return -2 - k if k >= 0 else stop


def again(h: str, n: str, i: int, en: int, st: int, dense: bool) -> int:
    # the next seek() of a loop over the occurrences of n that began at st: a stretch of memmem
    # first where memmem found the last one (dense)
    if dense:
        i = stretch(h, n, i, en, st)
        if i < 0:
            return i
    return seek(h, n, i, en, st)


def rsearch(h: str, n: str, st: int, en: int) -> int:
    # the last i from st on where n occurs in h[:en], or -1: runtime.c's loop, right to left,
    # with memcmp, which LLVM expands where the needle is a constant
    m = len(n)
    for k in range(en - m, st - 1, -1):
        if _rt.same(h, k, n, 0, m):
            return k
    return -1


def pys_str_find(h: str, n: str, st: int, en: int) -> int:
    st = adj_start(st, len(h))
    en = adj_end(en, len(h))
    if en - st < len(n):
        return -1
    return search(h, n, st, en)


def pys_str_rfind(h: str, n: str, st: int, en: int) -> int:
    return rsearch(h, n, adj_start(st, len(h)), adj_end(en, len(h)))


def pys_str_index(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_find(h, n, st, en)
    if i < 0:
        raise ValueError("substring not found")
    return i


def pys_str_rindex(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_rfind(h, n, st, en)
    if i < 0:
        raise ValueError("substring not found")
    return i


def pys_str_count(h: str, n: str, st: int, en: int) -> int:
    st = adj_start(st, len(h))
    en = adj_end(en, len(h))
    m = len(n)
    if en - st < m:
        return 0
    if m == 0:
        return en - st + 1
    first = _rt.byte(n, 0)
    c = 0
    if m == 1:
        # memchr from each occurrence to the next, 16 occurrences at a time, but an inline scan
        # (scan()) for the next 16 where those came within 4 bytes of each other on average: a call
        # for each is slow where they are that dense, and an inline scan mispredicts its exit at
        # each "<" of HTML
        k = _rt.find_byte(h, first, st, en)
        dense = False
        while k >= 0:
            j = k
            t = c + 16
            if dense:
                while k >= 0 and c < t:
                    c += 1
                    k = scan(h, first, k + 1, en)
            else:
                while k >= 0 and c < t:
                    c += 1
                    k = _rt.find_byte(h, first, k + 1, en)
            dense = k - j < 64
        return c
    # seek()'s loop, counting, without a call per occurrence
    last = en - m
    i = st
    while i <= last:
        paid = i - 64
        while True:
            if i > last:
                return c
            k = scan(h, first, i, last + 1)
            if k < 0:
                return c
            if match(h, k, n):
                c += 1
                i = k + m
            else:
                paid += toll(m)
                i = k + 1
                if paid > k:
                    break
        # stretch()'s memmem, from each occurrence it finds, then the candidates again
        while True:
            stop = reach(i, st, m)
            k = _rt.find_sub(h, n, i, en if stop > last else stop + m - 1)
            if k < 0:
                break
            c += 1
            i = k + m
        if stop > last:
            return c
        i = stop
    return c


def pys_str_contains(h: str, n: str) -> int:
    return 1 if len(n) <= len(h) and seek(h, n, 0, len(h), 0) != -1 else 0


def tail(s: str, p: str, st: int, en: int, end: bool) -> int:
    # CPython's tailmatch: s[st:en] starts (or ends) with p
    st = adj_start(st, len(s))
    en = adj_end(en, len(s))
    if en - len(p) < st:
        return 0
    return 1 if _rt.same(s, en - len(p) if end else st, p, 0, len(p)) else 0


def pys_str_startswith(s: str, p: str, st: int, en: int) -> int:
    return tail(s, p, st, en, False)


def pys_str_endswith(s: str, p: str, st: int, en: int) -> int:
    return tail(s, p, st, en, True)


def pys_str_replace(s: str, a: str, b: str) -> str:
    return replaced(s, a, b, -1) if len(a) > 0 else interleaved(s, b, -1)


def pys_str_replace_count(s: str, a: str, b: str, count: int) -> str:
    return replaced(s, a, b, count) if len(a) > 0 else interleaved(s, b, count)


def interleaved(s: str, b: str, count: int) -> str:
    # s.replace("", b, count), as CPython makes it: b before each of the first count characters,
    # and after the last one too where count is negative or more than their number. A character
    # is what uchar reads (bytes.replace() puts b between bytes: replaced()). An ASCII byte, and
    # a b of one byte, is a store, not a copy
    n = len(s)
    if count == 0:
        return s
    if count < 0 or count > n:
        count = n + 1  # (at least the places b can go)
    k = 0  # b goes before each of the k characters of s[:end], then once more at end
    end = 0
    while end < n and k < count - 1:
        end += 1 if _rt.byte(s, end) < 128 else uchar(s, end, n) & 7
        k += 1
    lb = len(b)
    c = _rt.byte(b, 0) if lb == 1 else 0
    r = _rt.str_new(n + (k + 1) * lb)
    at = 0
    i = 0
    while i < end:
        if lb == 1:
            _rt.str_put(r, at, c)
        elif lb > 1:
            _rt.copy(r, at, b, 0, lb)
        at += lb
        d = _rt.byte(s, i)
        if d < 128:
            _rt.str_put(r, at, d)
            at += 1
            i += 1
        else:
            m = uchar(s, i, n) & 7
            _rt.copy(r, at, s, i, m)
            at += m
            i += m
    _rt.copy(r, at, b, 0, lb)
    _rt.copy(r, at + lb, s, end, n - end)
    return _rt.str_done(r)


def tally(h: str, n: str, st: int, most: int) -> int:
    # pys_str_count(h, n, st, len(h)), up to most. One-byte needles use its optimized counting
    # loop in bounded chunks, so a small count does not search a long unchanged tail and a large
    # count keeps the same throughput. Multi-byte needles are counted by seek()'s
    # candidates; but -1 once the failed ones have cost more than the bytes passed (and 64), where
    # the count would go to memmem. replaced() then lists on: a text of costly candidates is
    # searched once, as before, not counted and searched again (DNA's "CA" in ACG took 1.6 times
    # as long, and "ab" * 70000 + "a" * 20000000 + "ab" 1.3 times)
    m = len(n)
    if m == 1:
        c = 0
        while st < len(h) and c < most:
            end = st + min(len(h) - st, max(65536, most - c))
            c += pys_str_count(h, n, st, end)
            st = end
        return min(c, most)
    first = _rt.byte(n, 0)
    last = len(h) - m
    c = 0
    i = st
    paid = st - 64
    while i <= last:
        k = scan(h, first, i, last + 1)
        if k < 0:
            break
        if match(h, k, n):
            c += 1
            if c == most:
                break
            i = k + m
        else:
            paid += toll(m)
            if paid > k:
                return -1
            i = k + 1
    return c


def replaced(s: str, a: str, b: str, count: int) -> str:
    # the first count occurrences of a replaced (all of them for a negative count), as CPython's
    # replace() makes them; an empty a as bytes.replace() puts it, between bytes
    n = len(s)
    if count == 0:
        return s
    if count < 0 or count > n:
        count = n + 1  # (more than a can occur)
    if len(a) == 0:
        # b before each of the first count - 1 bytes, and then once more (at the end, if count
        # reaches it)
        r = _rt.str_new(n + count * len(b))
        at = 0
        for i in range(count - 1):
            _rt.copy(r, at, b, 0, len(b))
            _rt.str_put(r, at + len(b), _rt.byte(s, i))
            at += len(b) + 1
        _rt.copy(r, at, b, 0, len(b))
        _rt.copy(r, at + len(b), s, count - 1, n - count + 1)
        return _rt.str_done(r)
    pos: list[int] = []  # where a occurs: one search pass, not one to count and one to copy
    dense = False
    j = 0
    cap = 65536  # occurrences listed before the list is weighed against the text it covers
    weigh = 16  # bytes per occurrence at most for replaced_dense(): 0 once tally() gives up
    while True:
        stop = count if count < cap else cap  # (the inner loop as before: its test the only one)
        while len(pos) < stop:
            j = again(s, a, j, n, 0, dense)
            if j == -1:
                break
            dense = j < -1
            if dense:
                j = -2 - j
            pos.append(j)
            j += len(a)
        if j == -1 or len(pos) == count:
            break
        if j <= cap * weigh:
            # A bounded count must stop counting at its limit, including for one-byte needles.
            rest = pys_str_count(s, a, j, n) if len(a) == 1 and count >= n else tally(s, a, j, count - len(pos))
            if rest >= 0:
                return replaced_dense(s, a, b, count, pos, rest)
            weigh = 0  # costly candidates (DNA's "CA" in ACG): searched once, listed
        cap *= 2  # sparse (long separators, lines): one pass, listed
    r = _rt.str_new(n + len(pos) * (len(b) - len(a)))
    i = 0
    at = 0
    for j in pos:
        _rt.copy(r, at, s, i, j - i)
        _rt.copy(r, at + j - i, b, 0, len(b))
        at += j - i + len(b)
        i = j + len(a)
    _rt.copy(r, at, s, i, n - i)
    return _rt.str_done(r)


def replaced_dense(s: str, a: str, b: str, count: int, pos: list[int], rest: int) -> str:
    # replaced() where its list pos of the first occurrences shows one every 16 bytes or more
    # often, so that a list of them all would outgrow the result ("*" * 10**7 replaced by "" took
    # 7.6 times runtime.c's memory), and rest more were counted after them: the result allocated
    # at its final size and each further occurrence copied into it as it is found, as runtime.c's
    # replace did. An empty gap or replacement costs no copy, and one byte of replacement a store.
    # The search is scan() and match(), not again(), whose seek() LLVM inlines into replaced()
    # only while that is its one caller: tally() found the failed candidates no costlier than
    # the bytes they passed, so these are the same candidates at the same cost
    n = len(s)
    m = len(a)
    lb = len(b)
    c = _rt.byte(b, 0) if lb == 1 else 0
    first = _rt.byte(a, 0)
    if rest > count - len(pos):
        rest = count - len(pos)
    r = _rt.str_new(n + (len(pos) + rest) * (lb - m))
    i = 0
    at = 0
    for t in range(len(pos) + rest):
        if t < len(pos):
            j = pos[t]
        else:
            j = scan(s, first, i, n - m + 1)
            while not match(s, j, a):
                j = scan(s, first, j + 1, n - m + 1)
        if j > i:
            _rt.copy(r, at, s, i, j - i)
            at += j - i
        if lb == 1:
            _rt.str_put(r, at, c)
        elif lb > 1:
            _rt.copy(r, at, b, 0, lb)
        at += lb
        i = j + m
    _rt.copy(r, at, s, i, n - i)
    return _rt.str_done(r)


def ws(c: int) -> bool:
    # an ASCII whitespace byte
    return c == 32 or (c >= 9 and c <= 13) or (c >= 28 and c <= 31)


def uchar(s: str, i: int, n: int) -> int:
    # the character at byte i of s[:n] (i < n), as runtime.c's u8char reads it: a UTF-8 sequence
    # as chr() writes it (no overlong form, nothing above U+10FFFF), else the one byte. Its code
    # point * 8 + its byte count
    c = _rt.byte(s, i)
    k = 1 if c > 244 else 4 if c >= 240 else 3 if c >= 224 else 2 if c >= 194 else 1
    if k == 1 or k > _rt.wrap_sub(n, i):
        return c * 8 + 1
    v = c & _rt.lshr(127, k)
    for j in range(1, k):
        b = _rt.byte(s, _rt.wrap_add(i, j))
        if b & 192 != 128:
            return c * 8 + 1
        v = _rt.shl(v, 6) | (b & 63)  # (below 2**21)
    if v < (128 if k == 2 else 2048 if k == 3 else 65536) or v > 1114111:
        return c * 8 + 1
    return _rt.shl(v, 3) | k


def utwo(s: str, i: int, c: int) -> int:
    # the two-byte character (U+0080 to U+07FF) of s that begins with the byte c at i, as uchar
    # reads it, else -1. utwo and uthree read most text that is not ASCII. Each calls nothing
    # and reads only bytes that it has compared with the length, which leaves no check that
    # could fail: they are small enough to become part of each loop that reads characters. Such
    # a loop steps by the count of the reader that succeeded, not by a count taken from the
    # bytes, so that the processor can begin the next character before this one is read
    if c > 193 and c < 224 and i >= 0 and _rt.wrap_add(i, 1) < len(s):
        b = _rt.byte(s, _rt.wrap_add(i, 1))
        if b & 192 == 128:
            return _rt.shl(c & 31, 6) | (b & 63)
    return -1


def uthree(s: str, i: int, c: int) -> int:
    # (utwo's, for the three-byte character, U+0800 to U+FFFF)
    if c > 223 and c < 240 and i >= 0 and _rt.wrap_add(i, 2) < len(s):
        b = _rt.byte(s, _rt.wrap_add(i, 1))
        d = _rt.byte(s, _rt.wrap_add(i, 2))
        if b & 192 == 128 and d & 192 == 128:
            v = _rt.shl(c & 15, 12) | _rt.shl(b & 63, 6) | (d & 63)
            if v > 2047:
                return v
    return -1


def pys_ascii(s: str) -> str:
    # ascii() receives repr's bytes: escape only its non-ASCII characters, with uchar's
    # one-byte fallback and surrogate handling. Count once, then fill one exact-size str.
    n = len(s)
    size = n
    first = n
    i = 0
    while i < n:
        if _rt.byte(s, i) < 128:
            i = _rt.wrap_add(i, 1)
            continue
        if first == n:
            first = i
        u = uchar(s, i, n)
        cp = _rt.lshr(u, 3)
        extra = (4 if cp < 256 else 6 if cp < 65536 else 10) - (u & 7)
        if size > _rt.wrap_sub(9223372036854775807, extra):
            raise MemoryError
        size = _rt.wrap_add(size, extra)
        i = _rt.wrap_add(i, u & 7)
    r = _rt.str_new(size)  # also checks the header and trailing NUL fit
    _rt.copy(r, 0, s, 0, first)  # the whole input when it is ASCII, still a fresh result
    at = first
    i = first
    while i < n:
        u = uchar(s, i, n)
        cp = _rt.lshr(u, 3)
        digits = 2 if cp < 256 else 4 if cp < 65536 else 8
        _rt.str_put(r, at, 92)
        _rt.str_put(r, _rt.wrap_add(at, 1), 120 if digits == 2 else 117 if digits == 4 else 85)
        for j in range(digits):
            d = _rt.lshr(cp, 4 * (digits - 1 - j)) & 15
            _rt.str_put(r, _rt.wrap_add(at, j + 2), (48 if d < 10 else 87) + d)
        at = _rt.wrap_add(at, digits + 2)
        i = _rt.wrap_add(i, u & 7)
        start = i
        while i < n and _rt.byte(s, i) < 128:
            i = _rt.wrap_add(i, 1)
        if i > start:
            count = _rt.wrap_sub(i, start)
            _rt.copy(r, at, s, start, count)
            at = _rt.wrap_add(at, count)
    return _rt.str_done(r)


def uspace(cp: int) -> bool:
    # str.isspace() of code point cp (Unicode 15.1, CPython 3.13): ASCII's and these
    if cp < 128:
        return ws(cp)
    return cp == 133 or cp == 160 or cp == 5760 or (cp >= 8192 and cp <= 8202) or cp == 8232 or cp == 8233 or cp == 8239 or cp == 8287 or cp == 12288


def wsat(s: str, i: int, n: int) -> int:
    # the character at byte i of s[:n] is whitespace: its byte count, else minus that (an ASCII
    # byte is tested inline; only a non-ASCII one is decoded)
    c = _rt.byte(s, i)
    if c < 128:
        return 1 if ws(c) else -1
    u = uchar(s, i, n)
    return u & 7 if uspace(_rt.lshr(u, 3)) else -(u & 7)


def back(s: str, j: int) -> int:
    # the byte count of the character that ends at byte j (j > 0): a UTF-8 sequence that ends
    # there, as uchar reads it, else one byte (runtime.c's uback)
    if _rt.byte(s, _rt.wrap_sub(j, 1)) < 128:
        return 1
    i = _rt.wrap_sub(j, 1)
    while i > 0 and _rt.wrap_sub(j, i) < 4 and _rt.byte(s, i) & 192 == 128:
        i = _rt.wrap_sub(i, 1)
    return _rt.wrap_sub(j, i) if uchar(s, i, j) & 7 == _rt.wrap_sub(j, i) else 1


def wsback(s: str, j: int) -> int:
    # as wsat, for the character that ends at byte j (j > 0)
    c = _rt.byte(s, _rt.wrap_sub(j, 1))
    if c < 128:
        return 1 if ws(c) else -1
    b = back(s, j)
    return wsat(s, _rt.wrap_sub(j, b), j)


def stripped(s: str, i: int, n: int, cs: str) -> int:
    # as wsat, for the characters of cs (whitespace if cs was omitted: null), so that a
    # character of several bytes is stripped whole or not at all, as CPython strips code points
    if _rt.null(cs):
        return wsat(s, i, n)
    c = _rt.byte(s, i)
    if c < 128:
        return 1 if _rt.find_byte(cs, c, 0, len(cs)) >= 0 else -1
    k = uchar(s, i, n) & 7
    j = 0
    while j < len(cs):
        m = uchar(cs, j, len(cs)) & 7
        if m == k and _rt.same(cs, j, s, i, m):
            return k
        j = _rt.wrap_add(j, m)
    return -k


def strip_byte(c: int, cs: str) -> bool:
    # whether strip() strips the ASCII byte c: whitespace if cs was omitted (null), else a byte of cs
    return ws(c) if _rt.null(cs) else _rt.find_byte(cs, c, 0, len(cs)) >= 0


def strip(s: str, cs: str, m: int) -> str:
    # m: 1 left, 2 right, 3 both; character by character (an ASCII byte tested here, see scan_ws)
    i = 0
    j = len(s)
    if m & 1:
        while i < j:
            c = _rt.byte(s, i)
            k = (1 if strip_byte(c, cs) else -1) if c < 128 else stripped(s, i, j, cs)
            if k < 0:
                break
            i = _rt.wrap_add(i, k)
    if m & 2:
        while j > i:
            c = _rt.byte(s, _rt.wrap_sub(j, 1))
            if c < 128:
                if not strip_byte(c, cs):
                    break
                j = _rt.wrap_sub(j, 1)
            else:
                b = back(s, j)
                if stripped(s, _rt.wrap_sub(j, b), j, cs) < 0:
                    break
                j = _rt.wrap_sub(j, b)
    return s[i:j]


def pys_str_strip(s: str, cs: str) -> str:
    return strip(s, cs, 3)


def pys_str_lstrip(s: str, cs: str) -> str:
    return strip(s, cs, 1)


def pys_str_rstrip(s: str, cs: str) -> str:
    return strip(s, cs, 2)


def digit(c: int) -> bool:
    return c >= 48 and c <= 57


def lowc(c: int) -> bool:
    return c >= 97 and c <= 122


def upc(c: int) -> bool:
    return c >= 65 and c <= 90


def pys_unicode_flags(cp: int) -> int: ...


def every(s: str, mask: int) -> int:
    # Every code point has a requested Unicode property, and there is at least one.
    # ASCII stays a byte scan; runtime.c's pys_unicode_flags supplies alpha=1, digit=2,
    # decimal=4, numeric=8.
    n = len(s)
    if n == 0:
        return 0
    i = 0
    while i < n:
        c = _rt.byte(s, i)
        if c < 128:
            if not ((mask & 14 != 0 and digit(c)) or (mask & 1 != 0 and lowc(c | 32))):
                return 0
            i = _rt.wrap_add(i, 1)
        else:
            k = 2
            cp = utwo(s, i, c)
            if cp < 0:
                k = 3
                cp = uthree(s, i, c)
                if cp < 0:
                    ch = uchar(s, i, n)
                    k = ch & 7
                    cp = _rt.lshr(ch, 3)
            if pys_unicode_flags(cp) & mask == 0:
                return 0
            i = _rt.wrap_add(i, k)
    return 1


def pys_unicode_case_flags(cp: int) -> int: ...


def pys_unicode_case_map(cp: int, kind: int) -> int: ...


def pys_unicode_case_ignorable(cp: int) -> int: ...


def uprev(s: str, i: int, n: int) -> int:
    # the character of s[:n] that ends before byte i (0 < i <= n), as uchar reads it going
    # forward: the sequence that the nearest byte before i that continues none begins, if it
    # ends at i; else the one byte before i, which begins no character
    j = _rt.wrap_sub(i, 1)
    while j > 0 and _rt.wrap_sub(i, j) < 4 and _rt.byte(s, j) & 192 == 128:
        j = _rt.wrap_sub(j, 1)
    u = uchar(s, j, n)
    if u & 7 == _rt.wrap_sub(i, j):
        return u
    return _rt.byte(s, _rt.wrap_sub(i, 1)) * 8 + 1


def ucontext(u: int) -> int:
    # the character uchar read as u in the context of a capital sigma: 1 where it is cased, 2
    # where it is case-ignorable (runtime.c's pys_unicode_case_ignorable). A byte that begins
    # no character is neither
    if u & 7 == 1 and u > 1023:
        return 0
    c = _rt.lshr(u, 3)
    return (1 if pys_unicode_case_flags(c) != 0 else 0) | (2 if pys_unicode_case_ignorable(c) != 0 else 0)


def final_sigma(s: str, i: int, n: int) -> bool:
    # whether the capital sigma at byte i of s[:n] lowers to the final form, as CPython's
    # handle_capital_sigma decides: a cased letter comes before it and none after it,
    # case-ignorable characters aside
    j = i
    before = False
    while j > 0:
        u = uprev(s, j, n)
        f = ucontext(u)
        if f & 2 == 0:
            before = f & 1 != 0
            break
        j = _rt.wrap_sub(j, u & 7)
    if not before:
        return False
    j = _rt.wrap_add(i, 2)
    while j < n:
        u = uchar(s, j, n)
        f = ucontext(u)
        if f & 2 == 0:
            return f & 1 == 0
        j = _rt.wrap_add(j, u & 7)
    return True


def uput(r: str, at: int, c: int, k: int) -> None:
    # code point c's k UTF-8 bytes (k > 1) into r from byte at
    if k == 2:
        _rt.str_put(r, at, 192 | _rt.lshr(c, 6))
    else:
        if k == 3:
            _rt.str_put(r, at, 224 | _rt.lshr(c, 12))
        else:
            _rt.str_put(r, at, 240 | _rt.lshr(c, 18))
            _rt.str_put(r, _rt.wrap_add(at, k - 3), 128 | (_rt.lshr(c, 12) & 63))
        _rt.str_put(r, _rt.wrap_add(at, k - 2), 128 | (_rt.lshr(c, 6) & 63))
    _rt.str_put(r, _rt.wrap_add(at, k - 1), 128 | (c & 63))


def mapu(s: str, how: int, r: str, room: int) -> int:
    # str's case methods as CPython maps each character (do_lower, do_upper, do_swapcase,
    # do_capitalize, do_title, do_casefold: how 0 to 5), for a str with bytes that are not
    # ASCII: the number of bytes of the result. It writes them into r while they fit its room
    # bytes, and gives -1 once they do not; with no room (-1) it only counts them. A character
    # that is not ASCII maps to one to three code points of 21 bits, the first lowest
    # (runtime.c's pys_unicode_case_map: kind 0 lower, 1 upper, 2 title, 3 casefold): each
    # character takes one mapping, which how chooses, and a capital sigma (U+03A3) lowers by
    # its context (CPython's lower_ucs4). A byte that begins no character is kept, and is no
    # letter
    n = len(s)
    i = 0
    at = 0
    prev = False  # (title: the character before is cased)
    fixed = 1 if how == 1 else 3 if how == 5 else 0  # (lower, upper and casefold: one mapping)
    while i < n:
        c = _rt.byte(s, i)
        k = 1
        cp = -1  # (the character where it is not ASCII)
        if c > 193:
            k = 2
            cp = utwo(s, i, c)
            if cp < 0:
                k = 3
                cp = uthree(s, i, c)
                if cp < 0:
                    u = uchar(s, i, n)
                    k = u & 7
                    if k > 1:
                        cp = _rt.lshr(u, 3)
        if cp < 0:
            # one byte: an ASCII character, mapped here, or a byte that begins no character
            if c > 127:
                prev = False
            elif how == 1:
                c = c & 223 if lowc(c) else c
            elif how == 0 or how == 5:
                c = c | 32 if upc(c) else c
            elif how == 2:
                c = c ^ 32 if lowc(c | 32) else c
            elif how == 3:
                c = (c & 223 if lowc(c) else c) if i == 0 else (c | 32 if upc(c) else c)
            else:
                letter = lowc(c | 32)
                c = (c | 32 if upc(c) else c) if prev else (c & 223 if lowc(c) else c)
                prev = letter
            if room >= 0:
                if at >= room:
                    return -1
                _rt.str_put(r, at, c)
            at = _rt.wrap_add(at, 1)
            i = _rt.wrap_add(i, 1)
            continue
        kind = fixed
        if how == 2:
            f = pys_unicode_case_flags(cp)
            kind = 0 if f & 1 != 0 else 1 if f & 2 != 0 else -1
        elif how == 3:
            kind = 2 if i == 0 else 0
        elif how == 4:
            kind = 0 if prev else 2
            prev = pys_unicode_case_flags(cp) != 0
        m = cp
        if kind == 0 and cp == 931:
            m = 962 if final_sigma(s, i, n) else 963
        elif kind >= 0:
            m = pys_unicode_case_map(cp, kind)
        if m == cp:
            # unchanged, as most characters of most text are: its bytes as they are
            if room >= 0:
                if _rt.wrap_add(at, k) > room:
                    return -1
                for j in range(k):
                    _rt.str_put(r, _rt.wrap_add(at, j), _rt.byte(s, _rt.wrap_add(i, j)))
            at = _rt.wrap_add(at, k)
        elif k == 2 and m > 127 and m < 2048:
            # (a two-byte character to another, as most that change do)
            if room >= 0:
                if _rt.wrap_add(at, 2) > room:
                    return -1
                _rt.str_put(r, at, 192 | _rt.lshr(m, 6))
                _rt.str_put(r, _rt.wrap_add(at, 1), 128 | (m & 63))
            at = _rt.wrap_add(at, 2)
        else:
            while True:
                c = m & 2097151
                w = 1 if c < 128 else 2 if c < 2048 else 3 if c < 65536 else 4
                if room >= 0:
                    if _rt.wrap_add(at, w) > room:
                        return -1
                    if w == 1:
                        _rt.str_put(r, at, c)
                    else:
                        uput(r, at, c, w)
                at = _rt.wrap_add(at, w)
                m = _rt.lshr(m, 21)
                if m == 0:
                    break
        i = _rt.wrap_add(i, k)
    return at


def upatch(s: str, how: int, r: str) -> bool:
    # The characters of s that are not ASCII, mapped in r, which holds s with its ASCII
    # characters mapped as how tells (0 lower, 1 upper, 2 swapcase, 3 capitalize, 5 casefold:
    # none of them maps an ASCII character by what is around it). A character that does not
    # change needs nothing, and most others map to as many bytes, which take its place.
    # False where a mapping has another count of bytes: r is then to be mapped anew (ucasemap)
    n = len(s)
    fixed = 1 if how == 1 else 3 if how == 5 else 0  # (lower, upper and casefold: one mapping)
    i = 0
    while i < n:
        c = _rt.byte(s, i)
        if c < 128:
            i = _rt.wrap_add(i, 1)
            continue
        k = 2
        cp = utwo(s, i, c)
        if cp < 0:
            k = 3
            cp = uthree(s, i, c)
            if cp < 0:
                u = uchar(s, i, n)
                k = u & 7
                if k == 1:
                    i = _rt.wrap_add(i, 1)
                    continue
                cp = _rt.lshr(u, 3)
        kind = fixed
        if how == 2:
            f = pys_unicode_case_flags(cp)
            kind = 0 if f & 1 != 0 else 1 if f & 2 != 0 else -1
        elif how == 3:
            kind = 2 if i == 0 else 0
        m = cp
        if kind == 0 and cp == 931:
            m = 962 if final_sigma(s, i, n) else 963
        elif kind >= 0:
            m = pys_unicode_case_map(cp, kind)
        if m != cp:
            if k == 2 and m > 127 and m < 2048:
                _rt.str_put(r, i, 192 | _rt.lshr(m, 6))
                _rt.str_put(r, _rt.wrap_add(i, 1), 128 | (m & 63))
            else:
                w = 0
                t = m
                while t != 0:
                    c = t & 2097151
                    w = _rt.wrap_add(w, 1 if c < 128 else 2 if c < 2048 else 3 if c < 65536 else 4)
                    t = _rt.lshr(t, 21)
                if w != k:
                    return False
                at = i
                while m != 0:
                    c = m & 2097151
                    w = 1 if c < 128 else 2 if c < 2048 else 3 if c < 65536 else 4
                    if w == 1:
                        _rt.str_put(r, at, c)
                    else:
                        uput(r, at, c, w)
                    at = _rt.wrap_add(at, w)
                    m = _rt.lshr(m, 21)
        i = _rt.wrap_add(i, k)
    return True


def umapped(s: str, how: int, r: str) -> str:
    # the result of a case method (upatch's how) for a str s with bytes that are not ASCII,
    # given r as that method's ASCII loop filled it
    if upatch(s, how, r):
        return _rt.str_done(r)
    return ucasemap(s, how, r)


def ucasemap(s: str, how: int, r: str) -> str:
    # mapu's result, given a new str r of s's size. Most mappings keep a character's size in
    # bytes, so r is filled first: it is the result where that fits exactly, and is copied where
    # the result is shorter. A longer result is counted, then filled. No character maps to more
    # than three times its bytes (tools/unicode_classification_tables.py checks each), so a str
    # whose result's size could not be counted is refused as an allocation of that size is
    # (MemoryError)
    n = len(s)
    size = mapu(s, how, r, n)
    if size == n:
        return _rt.str_done(r)
    if size < 0:
        if n > 3074457345618258602:
            _rt.str_new(-1)
        size = mapu(s, how, s, -1)
        r = _rt.str_new(size)
        mapu(s, how, r, size)
        return _rt.str_done(r)
    t = _rt.str_new(size)
    _rt.copy(t, 0, r, 0, size)
    return _rt.str_done(t)


def ucased(s: str, up: bool) -> int:
    # isupper / islower of a str with bytes that are not ASCII, as CPython tests each
    # character: none of the other case or titlecase, and one of this case
    n = len(s)
    seen = 0
    i = 0
    while i < n:
        c = _rt.byte(s, i)
        f = 0  # (upper 1, lower 2, titlecase 4: ASCII by its letters' ranges, the rest from runtime.c)
        k = 1
        if c < 128:
            if lowc(c | 32):
                f = 2 if c & 32 != 0 else 1
        else:
            k = 2
            cp = utwo(s, i, c)
            if cp < 0:
                k = 3
                cp = uthree(s, i, c)
                if cp < 0:
                    u = uchar(s, i, n)
                    k = u & 7
                    cp = _rt.lshr(u, 3)
            if k > 1:
                f = pys_unicode_case_flags(cp)
        if f & (6 if up else 5) != 0:
            return 0
        if f != 0:
            seen = 1
        i = _rt.wrap_add(i, k)
    return seen


def utitled(s: str) -> int:
    # istitle of a str with bytes that are not ASCII, as CPython's: an uppercase or titlecase
    # character only after an uncased one, a lowercase one only after a cased one, and one of
    # them
    n = len(s)
    prev = False
    seen = 0
    i = 0
    while i < n:
        c = _rt.byte(s, i)
        f = 0  # (ucased's)
        k = 1
        if c < 128:
            if lowc(c | 32):
                f = 2 if c & 32 != 0 else 1
        else:
            k = 2
            cp = utwo(s, i, c)
            if cp < 0:
                k = 3
                cp = uthree(s, i, c)
                if cp < 0:
                    u = uchar(s, i, n)
                    k = u & 7
                    cp = _rt.lshr(u, 3)
            if k > 1:
                f = pys_unicode_case_flags(cp)
        if f & 5 != 0:
            if prev:
                return 0
            prev = True
            seen = 1
        elif f != 0:
            if not prev:
                return 0
            prev = True
            seen = 1
        else:
            prev = False
        i = _rt.wrap_add(i, k)
    return seen


def nonascii(s: str) -> bool:
    # whether a byte of s is not ASCII (one reduction, which LLVM vectorizes)
    hi = False
    for i in range(len(s)):
        hi |= _rt.byte(s, i) > 127
    return hi


def cased(s: str, up: bool) -> int:
    # isupper / islower of ASCII letters; -1 for a letter of the other case, which decides
    # for any str, and 2 more where a byte is not ASCII. A str of fewer than 16 bytes, as most
    # are, gathers its bytes' union in the loop; a long one keeps the loop to its tests and is
    # scanned for such a byte only where it comes to an end (nonascii)
    seen = 0
    n = len(s)
    if n < 16:
        acc = 0
        for i in range(n):
            c = _rt.byte(s, i)
            acc |= c
            if lowc(c):
                if up:
                    return -1
                seen = 1
            if upc(c):
                if not up:
                    return -1
                seen = 1
        return seen | 2 if acc > 127 else seen
    for i in range(n):
        c = _rt.byte(s, i)
        if lowc(c):
            if up:
                return -1
            seen = 1
        if upc(c):
            if not up:
                return -1
            seen = 1
    return seen | 2 if nonascii(s) else seen


def pys_str_isdigit(s: str) -> int:
    return every(s, 2)


def pys_str_isalpha(s: str) -> int:
    return every(s, 1)


def pys_str_isalnum(s: str) -> int:
    return every(s, 15)


def pys_str_isspace(s: str) -> int:
    # all characters are whitespace (Unicode's, character by character), and there is one
    return 1 if len(s) > 0 and scan_ws(s, 0, len(s), False) == len(s) else 0


def pys_str_isupper(s: str) -> int:
    # ASCII letters decide where one is of the other case, or every byte is ASCII; else the
    # str's characters do, as CPython tests them (ucased): at once for a str that begins with
    # one that is not ASCII, as text in most scripts does
    if len(s) > 0 and _rt.byte(s, 0) > 127:
        return ucased(s, True)
    r = cased(s, True)
    if r < 0:
        return 0
    return ucased(s, True) if r > 1 else r


def pys_str_islower(s: str) -> int:
    if len(s) > 0 and _rt.byte(s, 0) > 127:
        return ucased(s, False)
    r = cased(s, False)
    if r < 0:
        return 0
    return ucased(s, False) if r > 1 else r


def pys_str_isdecimal(s: str) -> int:
    return every(s, 4)


def pys_str_isnumeric(s: str) -> int:
    return every(s, 8)


def pys_str_isascii(s: str) -> int:
    for i in range(len(s)):
        if _rt.byte(s, i) > 127:
            return 0
    return 1


def tolow(c: int) -> int:
    # The byte c, an ASCII upper-case letter lowered, with no test: bit 7 of c + 63 is set from
    # 'A' on and that of c + 37 from '[' on, so the first without the second marks the letters,
    # once the bytes above 127 are left out (c ^ 128); the letter's case is bit 5, two places
    # below. Every operation keeps to the byte's eight bits, which lets LLVM map sixteen bytes
    # in as many instructions, where a range test of the 64-bit value takes six times as many
    return c | _rt.lshr(_rt.wrap_add(c, 63) & (_rt.wrap_add(c, 37) ^ 128) & (c ^ 128) & 128, 2)


def toup(c: int) -> int:
    # (tolow's, for 'a' to 'z': an ASCII lower-case letter raised)
    return c ^ _rt.lshr(_rt.wrap_add(c, 31) & (_rt.wrap_add(c, 5) ^ 128) & (c ^ 128) & 128, 2)


def toswap(c: int) -> int:
    # (an ASCII letter of either case, which c | 32 makes a lower-case one: its case changed)
    d = c | 32
    return c ^ _rt.lshr(_rt.wrap_add(d, 31) & (_rt.wrap_add(d, 5) ^ 128) & (c ^ 128) & 128, 2)


def mapcase(s: str, how: int) -> str:
    # 0 lower, 1 upper, 2 swap: ASCII letters only (one loop per case, which LLVM vectorizes)
    n = len(s)
    r = _rt.str_new(n)
    if how == 0:
        for i in range(n):
            _rt.str_put(r, i, tolow(_rt.byte(s, i)))
    elif how == 1:
        for i in range(n):
            _rt.str_put(r, i, toup(_rt.byte(s, i)))
    else:
        for i in range(n):
            _rt.str_put(r, i, toswap(_rt.byte(s, i)))
    return _rt.str_done(r)


def mapstr(s: str, how: int, text: int) -> str:
    # mapcase for a long str: its loops, which also tell whether a byte is not ASCII. Such a str has
    # characters that CPython maps by their Unicode case, or bytes that begin none: umapped
    # (text: its how) maps those. LLVM still vectorizes each loop: it reads the length after the
    # allocation, as its index checks do, which leaves one bound, and |= of a bool is one
    # reduction of the bytes' width (or would branch)
    r = _rt.str_new(len(s))
    hi = False
    if how == 0:
        for i in range(len(s)):
            c = _rt.byte(s, i)
            hi |= c > 127
            _rt.str_put(r, i, tolow(c))
    elif how == 1:
        for i in range(len(s)):
            c = _rt.byte(s, i)
            hi |= c > 127
            _rt.str_put(r, i, toup(c))
    else:
        for i in range(len(s)):
            c = _rt.byte(s, i)
            hi |= c > 127
            _rt.str_put(r, i, toswap(c))
    if hi:
        return umapped(s, text, r)
    return _rt.str_done(r)


def pys_str_upper(s: str) -> str:
    # A str of fewer than 16 bytes, as most are, is mapped here: a test of each byte, which
    # costs such a str less than the call and the operations that mapstr's loops are
    # vectorized for. The bytes' union tells whether one is not ASCII (umapped then)
    n = len(s)
    if n > 15:
        return mapstr(s, 1, 1)
    r = _rt.str_new(n)
    acc = 0
    for i in range(n):
        c = _rt.byte(s, i)
        acc |= c
        _rt.str_put(r, i, c & 223 if lowc(c) else c)
    return umapped(s, 1, r) if acc > 127 else _rt.str_done(r)


def pys_str_lower(s: str) -> str:
    n = len(s)
    if n > 15:
        return mapstr(s, 0, 0)
    r = _rt.str_new(n)
    acc = 0
    for i in range(n):
        c = _rt.byte(s, i)
        acc |= c
        _rt.str_put(r, i, c | 32 if upc(c) else c)
    return umapped(s, 0, r) if acc > 127 else _rt.str_done(r)


def pys_str_casefold(s: str) -> str:
    n = len(s)
    if n > 15:
        return mapstr(s, 0, 5)
    r = _rt.str_new(n)
    acc = 0
    for i in range(n):
        c = _rt.byte(s, i)
        acc |= c
        _rt.str_put(r, i, c | 32 if upc(c) else c)
    return umapped(s, 5, r) if acc > 127 else _rt.str_done(r)


def pys_str_swapcase(s: str) -> str:
    n = len(s)
    if n > 15:
        return mapstr(s, 2, 2)
    r = _rt.str_new(n)
    acc = 0
    for i in range(n):
        c = _rt.byte(s, i)
        acc |= c
        _rt.str_put(r, i, c ^ 32 if lowc(c | 32) else c)
    return umapped(s, 2, r) if acc > 127 else _rt.str_done(r)


def pys_str_capitalize(s: str) -> str:
    # ASCII letters, the first raised and the others lowered; a str with any other byte by its
    # characters (umapped). A short str by a test of each byte, as pys_str_upper's; a long one
    # lowered as mapstr's loop does, then its first byte raised
    n = len(s)
    r = _rt.str_new(len(s))
    if n < 16:
        acc = 0
        for i in range(n):
            c = _rt.byte(s, i)
            acc |= c
            if (i == 0 and lowc(c)) or (i > 0 and upc(c)):
                c ^= 32
            _rt.str_put(r, i, c)
        return umapped(s, 3, r) if acc > 127 else _rt.str_done(r)
    hi = False
    for i in range(len(s)):
        c = _rt.byte(s, i)
        hi |= c > 127
        _rt.str_put(r, i, tolow(c))
    _rt.str_put(r, 0, toup(_rt.byte(s, 0)))
    if hi:
        return umapped(s, 3, r)
    return _rt.str_done(r)


def pys_str_title(s: str) -> str:
    # a letter after a letter is lowered, any other raised: ASCII letters, unless a byte is not
    # ASCII, when CPython's characters tell (ucasemap): at once for a str that begins with such
    # a byte, as text in most scripts does
    n = len(s)
    r = _rt.str_new(len(s))
    if n > 0 and _rt.byte(s, 0) > 127:
        return ucasemap(s, 4, r)
    prev = False
    if n < 16:
        # (a short str, as most are: its bytes' union, gathered in the loop)
        acc = 0
        for i in range(n):
            c = _rt.byte(s, i)
            acc |= c
            if (prev and upc(c)) or (not prev and lowc(c)):
                _rt.str_put(r, i, c ^ 32)
            else:
                _rt.str_put(r, i, c)
            prev = lowc(c) or upc(c)
        return ucasemap(s, 4, r) if acc > 127 else _rt.str_done(r)
    if nonascii(s):
        return ucasemap(s, 4, r)
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (prev and upc(c)) or (not prev and lowc(c)):
            _rt.str_put(r, i, c ^ 32)
        else:
            _rt.str_put(r, i, c)
        prev = lowc(c) or upc(c)
    return _rt.str_done(r)


def pys_str_istitle(s: str) -> int:
    # CPython's istitle, over ASCII letters. A byte that is not ASCII may be of a cased
    # character, which the letters after it follow: the str's characters tell then (utitled)
    prev = False
    seen = 0
    hi = False
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if upc(c):
            if prev:
                return utitled(s) if hi else 0
            prev = True
            seen = 1
        elif lowc(c):
            if not prev:
                return utitled(s) if hi else 0
            prev = True
            seen = 1
        else:
            prev = False
            if c > 127:
                hi = True
    return utitled(s) if hi else seen


def pys_text_len(s: str) -> int: ...


def ulen(s: str) -> int:
    # the length in characters: runtime.c's count, which len() gives (u8char's characters, as
    # uchar reads them, counted once and kept in the str)
    return pys_text_len(s)


def fillrun(r: str, at: int, fill: str, count: int) -> None:
    # count copies of fill into r from byte at: one copy, then copies of what is there, doubling
    total = count * len(fill)
    if total <= 0:
        return
    _rt.copy(r, at, fill, 0, len(fill))
    done = len(fill)
    while done < total:
        k = done if done <= total - done else total - done
        _rt.copy(r, at + done, r, at, k)
        done += k


def pad(s: str, w: int, fill: str, how: int) -> str:
    # how: 0 right, 1 left, 2 center; widths count characters; fill is null for a space
    if not _rt.null(fill) and ulen(fill) != 1:
        raise TypeError("The fill character must be exactly one character long")
    f = " " if _rt.null(fill) else fill
    n = ulen(s)
    if n >= w:
        return s
    gap = w - n
    left = 0 if how == 1 else gap if how == 0 else gap // 2 + (gap & w & 1)  # CPython's centering
    if len(f) == 1:
        # one byte: stores that LLVM turns into memset, and calls small enough to inline
        if gap > 9223372036854775807 - len(s):
            raise MemoryError
        c = _rt.byte(f, 0)
        r = _rt.str_new(len(s) + gap)
        for i in range(left):
            _rt.str_put(r, i, c)
        _rt.copy(r, left, s, 0, len(s))
        for i in range(left + len(s), len(s) + gap):
            _rt.str_put(r, i, c)
        return _rt.str_done(r)
    if gap > (9223372036854775807 - len(s)) // len(f):
        raise MemoryError
    r = _rt.str_new(len(s) + gap * len(f))
    fillrun(r, 0, f, left)
    _rt.copy(r, left * len(f), s, 0, len(s))
    fillrun(r, left * len(f) + len(s), f, gap - left)
    return _rt.str_done(r)


def pys_str_ljust(s: str, w: int, fill: str) -> str:
    return pad(s, w, fill, 1)


def pys_str_rjust(s: str, w: int, fill: str) -> str:
    return pad(s, w, fill, 0)


def pys_str_center(s: str, w: int, fill: str) -> str:
    return pad(s, w, fill, 2)


def pys_str_zfill(s: str, w: int) -> str:
    n = ulen(s)
    if n >= w:
        return s
    z = w - n
    if z > 9223372036854775807 - len(s):
        raise MemoryError
    r = _rt.str_new(len(s) + z)
    fillrun(r, 0, "0", z)
    _rt.copy(r, z, s, 0, len(s))
    if len(s) > 0 and (_rt.byte(s, 0) == 43 or _rt.byte(s, 0) == 45):
        # a sign moves in front of the zeros
        _rt.str_put(r, 0, _rt.byte(s, 0))
        _rt.str_put(r, z, 48)
    return _rt.str_done(r)


def pys_str_partition(s: str, sep: str) -> tuple[str, str, str]:
    if len(sep) == 0:
        raise ValueError("empty separator")
    i = search(s, sep, 0, len(s)) if len(sep) <= len(s) else -1
    if i < 0:
        return (s, "", "")
    return (s[:i], sep, s[i + len(sep) :])


def pys_str_rpartition(s: str, sep: str) -> tuple[str, str, str]:
    if len(sep) == 0:
        raise ValueError("empty separator")
    i = rsearch(s, sep, 0, len(s))
    if i < 0:
        return ("", "", s)
    return (s[:i], sep, s[i + len(sep) :])


def pys_str_removeprefix(s: str, p: str) -> str:
    if len(p) > 0 and len(s) >= len(p) and _rt.same(s, 0, p, 0, len(p)):
        return s[len(p) :]
    return s


def pys_str_removesuffix(s: str, p: str) -> str:
    if len(p) > 0 and len(s) >= len(p) and _rt.same(s, len(s) - len(p), p, 0, len(p)):
        return s[: len(s) - len(p)]
    return s


def pys_str_expandtabs(s: str, size: int) -> str:
    if size > 2147483647 or size < -2147483648:
        raise OverflowError("Python int too large to convert to C int")  # CPython's C int
    # two passes: the length, then the bytes
    r = _rt.str_new(0)
    for k in range(2):
        col = 0
        at = 0
        more = 0  # the bytes left of a character of several, as uchar reads it (one column)
        for i in range(len(s)):
            c = _rt.byte(s, i)
            if c == 9:
                if size > 0:
                    sp = size - col % size
                    col += sp
                    for _ in range(sp if k == 1 else 0):
                        _rt.str_put(r, at, 32)
                        at += 1
                    at += sp if k == 0 else 0
            else:
                if k == 1:
                    _rt.str_put(r, at, c)
                at += 1
                if c == 10 or c == 13:
                    col = 0
                elif more > 0:
                    more -= 1
                else:
                    col += 1
                    if c > 127:
                        more = (uchar(s, i, len(s)) & 7) - 1
        if k == 0:
            r = _rt.str_new(at)
    return _rt.str_done(r)


def pys_str_join(sep: str, l: list[str]) -> str:
    # iterating (no index checks), and a separator of one byte stored as a byte
    m = len(sep)
    n = 0
    i = 0
    for x in l:
        if _rt.null(x):
            # an item of a list[str | None]
            raise TypeError("sequence item " + str(i) + ": expected str instance, NoneType found")
        n += len(x)
        i += 1
    if len(l) > 1:
        n += m * (len(l) - 1)
    r = _rt.str_new(n)
    at = 0
    c = _rt.byte(sep, 0) if m == 1 else -1
    first = True
    for x in l:
        if not first and m > 0:
            if c >= 0:
                _rt.str_put(r, at, c)
            else:
                _rt.copy(r, at, sep, 0, m)
            at += m
        first = False
        _rt.copy(r, at, x, 0, len(x))
        at += len(x)
    return _rt.str_done(r)


def pys_str_split(s: str, sep: str, maxsplit: int) -> list[str]:
    # maxsplit < 0: no limit
    out: list[str] = []
    i = 0
    n = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if _rt.null(sep):
        while True:
            i = scan_ws(s, i, n, False)
            if i >= n:
                return out
            if left == 0:
                out.append(s[i:])  # the rest, as it is
                return out
            left -= 1
            j = scan_ws(s, i, n, True)
            out.append(s[i:j])
            i = j
    if len(sep) == 0:
        raise ValueError("empty separator")
    c = _rt.byte(sep, 0) if len(sep) == 1 else -1
    dense = False
    while left != 0:
        if c >= 0:
            j = _rt.find_byte(s, c, i, n)  # one byte: memchr, no search setup per part
        else:
            j = again(s, sep, i, n, 0, dense)
            dense = j < -1
            if dense:
                j = -2 - j
        if j < 0:
            break
        left -= 1
        out.append(s[i:j])
        i = j + len(sep)
    out.append(s[i:])
    return out


def pys_str_split_first(s: str, sep: str, maxsplit: int) -> str:
    # s.split(sep, maxsplit)[0] (Gen.index): pys_str_split's first part, without the list or the
    # other parts. Without sep, the first word (none: the list is empty, which [0] raises for)
    n = len(s)
    if _rt.null(sep):
        i = scan_ws(s, 0, n, False)
        if i >= n:
            raise IndexError("list index out of range")
        return s[i:] if maxsplit == 0 else s[i : scan_ws(s, i, n, True)]
    if len(sep) == 0:
        raise ValueError("empty separator")
    j = search(s, sep, 0, n) if maxsplit != 0 else -1
    return s[:j] if j >= 0 else s  # (no sep: s itself, as CPython's list holds it)


def pys_str_rsplit(s: str, sep: str, maxsplit: int) -> list[str]:
    # split from the right; the parts stay in order
    out: list[str] = []
    j = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if _rt.null(sep):
        while True:
            while j > 0:
                c = _rt.byte(s, _rt.wrap_sub(j, 1))
                b = (1 if ws(c) else -1) if c < 128 else wsback(s, j)
                if b < 0:
                    break
                j = _rt.wrap_sub(j, b)
            if j <= 0:
                break
            if left == 0:
                out.append(s[:j])
                break
            left -= 1
            i = j
            while i > 0:
                c = _rt.byte(s, _rt.wrap_sub(i, 1))
                b = (1 if ws(c) else -1) if c < 128 else wsback(s, i)
                if b > 0:
                    break
                i = _rt.wrap_add(i, b)
            out.append(s[i:j])
            j = i
    else:
        if len(sep) == 0:
            raise ValueError("empty separator")
        while left != 0:
            i = rsearch(s, sep, 0, j)
            if i < 0:
                break
            left -= 1
            out.append(s[i + len(sep) : j])
            j = i
        out.append(s[:j])
    out.reverse()
    return out


def eol(s: str, i: int) -> int:
    # the length of the line break at i, 0 if none
    c = _rt.byte(s, i)
    left = len(s) - i
    if c == 13:
        return 2 if left > 1 and _rt.byte(s, i + 1) == 10 else 1
    if c == 10 or c == 11 or c == 12 or (c >= 28 and c <= 30):
        return 1
    if c == 194 and left > 1 and _rt.byte(s, i + 1) == 133:
        return 2  # U+0085
    if c == 226 and left > 2 and _rt.byte(s, i + 1) == 128 and (_rt.byte(s, i + 2) == 168 or _rt.byte(s, i + 2) == 169):
        return 3  # U+2028, U+2029
    return 0


def pys_str_splitlines(s: str, keep: int) -> list[str]:
    out: list[str] = []
    i = 0
    st = 0
    while i < len(s):
        c = _rt.byte(s, i)
        if c > 30 and c != 194 and c != 226:
            i += 1  # no line break starts with c
            continue
        k = eol(s, i)
        if k == 0:
            i += 1
            continue
        out.append(s[st : i + (k if keep != 0 else 0)])
        i += k
        st = i
    if st < len(s):
        out.append(s[st:])
    return out


# ---------- os.path: posixpath's string functions ----------
# CPython 3.13's posixpath (and genericpath), step for step, on the bytes of a str: "/" and "."
# are single bytes that occur in no other character's encoding.


def pys_getcwd() -> str: ...


def pys_path_join(a: str, b: str) -> str:
    # os.path.join(a, b), as posixpath.join steps through its parts: b alone if it is absolute
    # or a is empty, else a, a "/" unless a ends with one, and b
    if len(a) == 0 or (len(b) > 0 and _rt.byte(b, 0) == 47):
        return b
    if _rt.byte(a, len(a) - 1) == 47:
        return a + b
    n = len(a)
    r = _rt.str_new(_rt.wrap_add(_rt.wrap_add(n, 1), len(b)))
    _rt.copy(r, 0, a, 0, n)
    _rt.str_put(r, n, 47)
    _rt.copy(r, _rt.wrap_add(n, 1), b, 0, len(b))
    return _rt.str_done(r)


def last_part(p: str) -> int:
    # p.rfind("/") + 1: where p's last component starts
    i = len(p)
    while i > 0 and _rt.byte(p, i - 1) != 47:
        i -= 1
    return i


def path_head(p: str, i: int) -> str:
    # split()'s and dirname()'s head of p, whose last component starts at i: p[:i] without its
    # trailing slashes, unless it is slashes only
    j = i
    while j > 0 and _rt.byte(p, j - 1) == 47:
        j -= 1
    return p[:i] if j == 0 else p[:j]


def pys_path_basename(p: str) -> str:
    return p[last_part(p) :]


def pys_path_dirname(p: str) -> str:
    return path_head(p, last_part(p))


def pys_path_split(p: str) -> tuple[str, str]:
    i = last_part(p)
    return (path_head(p, i), p[i:])


def pys_path_splitext(p: str) -> tuple[str, str]:
    # genericpath._splitext: at the last dot of the last component, unless only dots precede it
    i = last_part(p)
    d = len(p) - 1
    while d >= i and _rt.byte(p, d) != 46:
        d -= 1
    k = i
    while k < d and _rt.byte(p, k) == 46:
        k += 1
    if k < d:
        return (p[:d], p[d:])
    return (p, "")


def pys_path_isabs(p: str) -> int:
    return 1 if len(p) > 0 and _rt.byte(p, 0) == 47 else 0


def pys_path_normpath(p: str) -> str:
    n = len(p)
    if n == 0:
        return "."
    # splitroot(): no root, "/" for one leading slash or three and more, "//" for exactly two
    root = 0
    if _rt.byte(p, 0) == 47:
        root = 2 if n >= 2 and _rt.byte(p, 1) == 47 and (n == 2 or _rt.byte(p, 2) != 47) else 1
    comps: list[str] = []
    i = root
    while i <= n:
        j = _rt.find_byte(p, 47, i, n)
        if j < 0:
            j = n
        m = j - i
        if m == 0 or (m == 1 and _rt.byte(p, i) == 46):
            pass  # ("" and ".")
        elif not (m == 2 and _rt.byte(p, i) == 46 and _rt.byte(p, i + 1) == 46) or (root == 0 and len(comps) == 0) or (len(comps) > 0 and comps[-1] == ".."):
            comps.append(p[i:j])
        elif len(comps) > 0:
            comps.pop()  # (".." after a name; at the root it is dropped)
        i = j + 1
    out = p[:root] + "/".join(comps)
    return out if len(out) > 0 else "."


def pys_path_abspath(p: str) -> str:
    if len(p) == 0 or _rt.byte(p, 0) != 47:
        p = pys_path_join(pys_getcwd(), p)
    return pys_path_normpath(p)


def path_parts(p: str) -> list[str]:
    # relpath()'s p.lstrip("/").split("/") of an abspath() p, [] where nothing follows the slashes
    out: list[str] = []
    n = len(p)
    i = 0
    while i < n and _rt.byte(p, i) == 47:
        i += 1
    while i < n:
        j = _rt.find_byte(p, 47, i, n)
        if j < 0:
            j = n
        out.append(p[i:j])
        i = j + 1
    return out


def pys_path_relpath(p: str, start: str) -> str:
    if len(p) == 0:
        raise ValueError("no path specified")
    a = path_parts(pys_path_abspath(start))
    b = path_parts(pys_path_abspath(p))
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    out: list[str] = []
    for _ in range(len(a) - i):
        out.append("..")
    for k in range(i, len(b)):
        out.append(b[k])
    return "/".join(out) if len(out) > 0 else "."


def pys_path_commonprefix(m: list[str]) -> str:
    # genericpath.commonprefix: the characters that the least and the greatest str share at their
    # starts (bytes order strs as their code points do)
    if len(m) == 0:
        return ""
    lo = m[0]
    hi = m[0]
    for x in m:
        if x < lo:
            lo = x
        if x > hi:
            hi = x
    n = len(lo)  # (lo <= hi: hi is no proper prefix of lo)
    i = 0
    while i < n and i < len(hi) and _rt.byte(lo, i) == _rt.byte(hi, i):
        i += 1
    while i > 0 and i < n and (_rt.byte(lo, i) & 192) == 128:
        i -= 1  # (inside a character whose bytes differ later: back to its first byte)
    return lo[:i]


# ---------- dict hashing ----------
# The hash of a str and the mix of an int's bits that the dicts and sets below use. The
# arithmetic wraps, as C's unsigned arithmetic does, and the shifts are logical.


def pys_hash_str(s: str) -> int:
    # FNV-1a over the bytes, with the high bits folded into the low ones that pick a slot
    h = 1469598103934665603
    for i in range(len(s)):
        h = _rt.wrap_mul(h ^ _rt.byte(s, i), 1099511628211)
    return h ^ _rt.lshr(h, 29)


def pys_hash_int(k: int) -> int:
    # a round of SplitMix64's mixer (0xBF58476D1CE4E5B9 is -4658895280553007687 as a 64-bit int)
    h = _rt.wrap_mul(k ^ _rt.lshr(k, 30), -4658895280553007687)
    return h ^ _rt.lshr(h, 31)


# ---------- int and its text: str(i) and int(s, base) ----------
# The digits are written and read here. runtime.c keeps the two steps that need its tables and
# its repr: what a str that is not ASCII becomes first (pys_num_ascii), and the error for a str
# that is no int (pys_int_badlit, which does not return).


def pys_str_int(v: int) -> str:
    # str(v). The digits of |v|, an unsigned 64-bit pattern (-2**63's is its own), are counted
    # and then written from the last one. The arithmetic wraps where it cannot overflow, so
    # that nothing here raises but the allocation
    neg = 1 if v < 0 else 0
    u = _rt.wrap_sub(0, v) if v < 0 else v
    n = neg
    q = u
    while True:
        n = _rt.wrap_add(n, 1)
        q = _rt.udiv(q, 10)
        if q == 0:
            break
    r = _rt.str_new(n)
    if neg != 0:
        _rt.str_put(r, 0, 45)
    for i in range(n - 1, neg - 1, -1):
        _rt.str_put(r, i, _rt.wrap_add(48, _rt.urem(u, 10)))
        u = _rt.udiv(u, 10)
    return _rt.str_done(r)


def numws(c: int) -> bool:
    # the whitespace that int() and float() strip around a number, and no other
    return c == 32 or (c >= 9 and c <= 13)


def digitv(c: int) -> int:
    # the value of byte c as a digit of a base up to 36, or 99. Both readings are computed and
    # one is selected: a branch on digit or letter is mispredicted for hex digits
    d = _rt.wrap_sub(c, 48)
    a = _rt.wrap_sub(c | 32, 87)
    if a < 10 or a > 35:
        a = 99
    return d if d >= 0 and d < 10 else a


def pys_num_ascii(s: str) -> str: ...
def pys_int_badlit(s: str, base: int) -> None: ...


def pys_int_str(s: str, base: int) -> int:
    # int(s, base): CPython's PyLong_FromString on the ASCII form of s, with its checks in its
    # order. Base 0 takes the base from a prefix, and then only 0 may begin with a 0 (octal)
    if base != 0 and (base < 2 or base > 36):
        raise ValueError("int() base must be >= 2 and <= 36, or 0")
    t = pys_num_ascii(s) if nonascii(s) else s
    p = 0
    e = len(t)
    while p < e and numws(_rt.byte(t, p)):
        p += 1
    while e > p and numws(_rt.byte(t, e - 1)):
        e -= 1
    neg = False
    if p < e and (_rt.byte(t, p) == 43 or _rt.byte(t, p) == 45):
        neg = _rt.byte(t, p) == 45
        p += 1
    b = base
    if e - p >= 2 and _rt.byte(t, p) == 48:
        x = _rt.byte(t, p + 1) | 32
        pb = 16 if x == 120 else 8 if x == 111 else 2 if x == 98 else 0
        if pb != 0 and (b == 0 or b == pb):
            b = pb
            p += 2
            if p < e and _rt.byte(t, p) == 95:
                p += 1
    octal = False
    if b == 0:
        b = 10
        octal = p < e and _rt.byte(t, p) == 48
    # The value is gathered below zero, where -2**63 has room. lim is the least it may be, and
    # digit d fits where acc * b - d >= lim, which cut and rest (|lim| divided by b) decide
    # without a division for each digit. A digit that does not fit leaves acc as it is
    lim = -9223372036854775807 - 1 if neg else -9223372036854775807
    cut = _rt.wrap_sub(0, _rt.udiv(_rt.wrap_sub(0, lim), b))
    rest = _rt.urem(_rt.wrap_sub(0, lim), b)
    acc = 0
    nd = 0
    ovf = False
    prev = 0
    q = p
    while q < e:  # digits, with single underscores between them
        c = _rt.byte(t, q)
        d = digitv(c)
        if d < b:
            nd += 1
            if acc < cut or (acc == cut and d > rest):
                ovf = True
            else:
                acc = _rt.wrap_sub(_rt.wrap_mul(acc, b), d)
        elif c != 95 or q == p or prev == 95:
            break
        prev = c
        q += 1
    while q < e and numws(_rt.byte(t, q)):  # whitespace before a NUL, where CPython's C string ends
        q += 1
    if nd == 0 or prev == 95 or (q < e and _rt.byte(t, q) != 0):
        pys_int_badlit(s, base)
    if b & (b - 1) != 0 and nd > 4300:  # CPython's limit for its quadratic conversion
        raise ValueError(f"Exceeds the limit (4300 digits) for integer string conversion: value has {nd} digits; use sys.set_int_max_str_digits() to increase the limit")
    if q < e or (octal and acc != 0):
        pys_int_badlit(s, base)
    if ovf:
        raise OverflowError("int() result does not fit in 64 bits")
    return acc if neg else _rt.wrap_sub(0, acc)


# ---------- formatting: f"{x:spec}" ----------
# CPython's format-spec mini-language for int (and bool), float and str:
# [[fill]align][sign][z][#][0][width][grouping][.precision][type]. Widths count code points.
# runtime.c's pys_format calls these by the value's type (other types accept only an empty spec),
# and the digits of a float come from runtime.c's pys_fmt_float, which uses snprintf.


def pys_fmt_float(m: float, ty: int, prec: int, alt: int) -> str: ...


def uoff(s: str, k: int) -> int:
    # the byte offset of character k, as uchar reads characters
    n = len(s)
    i = 0
    while i < n and k > 0:
        i += 1 if _rt.byte(s, i) < 128 else uchar(s, i, n) & 7
        k -= 1
    return i


def utf8(c: int) -> str:
    # code point c in UTF-8 (chr(c) is the byte itself below 256)
    if c < 128:
        return chr(c)
    n = 2 if c < 2048 else 3 if c < 65536 else 4
    r = _rt.str_new(n)
    _rt.str_put(r, 0, (c >> 6 * (n - 1)) | (65280 >> n & 255))
    for i in range(1, n):
        _rt.str_put(r, i, 128 | (c >> 6 * (n - 1 - i) & 63))
    return _rt.str_done(r)


def among(c: int, cs: str) -> bool:
    # whether byte c is one of cs, or the end of the spec (0), as strchr finds C's terminator
    return c == 0 or _rt.find_byte(cs, c, 0, len(cs)) >= 0


def ucode(s: str, i: int) -> int:
    # the code point of the character at byte i, as uchar reads it (a byte that begins none is
    # the character chr() makes of it)
    return uchar(s, i, len(s)) >> 3


def tych(c: int) -> str:
    # a presentation type in a message, as CPython writes it: '\\x%x' outside 33..127
    if c > 32 and c < 128:
        return chr(c)
    h = ""
    q = c
    while True:
        h = "0123456789abcdef"[q % 16] + h
        q = q // 16
        if q == 0:
            break
    return "\\x" + h


def known(c: int, cs: str) -> bool:
    # whether code point c is one of the ASCII codes cs
    return c > 0 and c < 128 and _rt.find_byte(cs, c, 0, len(cs)) >= 0


def tyname(kind: int) -> str:
    return "int" if kind == 0 or kind == 4 else "bool" if kind == 1 else "float" if kind == 2 else "str"


def group(dg: str, sep: int, every: int, minw: int) -> str:
    # digits with a separator every `every` of them, zero-padded (separators included) to minw
    n = len(dg)
    z = 0
    total = n + ((n - 1) // every if sep != 0 else 0)
    while total < minw:
        z += 1
        total = n + z + ((n + z - 1) // every if sep != 0 else 0)
    r = _rt.str_new(total)
    at = 0
    for i in range(n + z):
        _rt.str_put(r, at, 48 if i < z else _rt.byte(dg, i - z))
        at += 1
        if sep != 0 and (n + z - i - 1) % every == 0 and i < n + z - 1:
            _rt.str_put(r, at, sep)
            at += 1
    return _rt.str_done(r)


def zero(t: str) -> bool:
    # whether the digits of t, up to an exponent or %, are all zero
    for i in range(len(t)):
        c = _rt.byte(t, i)
        if c == 101 or c == 69 or c == 37:
            return True
        if c >= 49 and c <= 57:
            return False
    return True


def fmt(kind: int, iv: int, fv: float, sv: str, spec: str) -> str:
    # kind: 0 int, 1 bool, 2 float, 3 str (iv, fv or sv is the value), 4 an int past 64 bits:
    # its sign in iv (-1 or 1) and its magnitude's digits in sv, in the base of the spec's type
    # (pys_big_format, which formats the float types and 'c' itself)
    n = len(spec)
    p = 0
    fill = " "
    align = 0
    fillset = False
    cl = uoff(spec, 1)
    if cl > 0 and cl < n and _rt.byte(spec, cl) != 0 and among(_rt.byte(spec, cl), "<>=^"):
        fill = spec[:cl]
        fillset = True
        align = _rt.byte(spec, cl)
        p = cl + 1
    elif n > 0 and _rt.byte(spec, 0) != 0 and among(_rt.byte(spec, 0), "<>=^"):
        align = _rt.byte(spec, 0)
        p = 1
    sign = 0
    if p < n and (_rt.byte(spec, p) == 43 or _rt.byte(spec, p) == 45 or _rt.byte(spec, p) == 32):
        sign = _rt.byte(spec, p)
        p += 1
    zneg = False
    if p < n and _rt.byte(spec, p) == 122:
        zneg = True
        p += 1
    alt = False
    if p < n and _rt.byte(spec, p) == 35:
        alt = True
        p += 1
    numeric = kind != 3
    if p < n and _rt.byte(spec, p) == 48:
        # zero padding: fill '0', and '=' alignment for numbers
        if not fillset:
            fill = "0"
            if align == 0 and numeric:
                align = 61
        p += 1
    width = 0
    while p < n and digit(_rt.byte(spec, p)):
        width = width * 10 + _rt.byte(spec, p) - 48
        p += 1
        if width > 100000000:
            raise ValueError("Too many decimal digits in format string")
    sep = 0  # ',' then '_', as CPython reads them: a second ',' or '_' is the type, which it rejects below
    if p < n and _rt.byte(spec, p) == 44:
        sep = 44
        p += 1
    if p < n and _rt.byte(spec, p) == 95:
        if sep != 0:
            raise ValueError("Cannot specify both ',' and '_'.")
        sep = 95
        p += 1
    if p < n and _rt.byte(spec, p) == 44 and sep == 95:
        raise ValueError("Cannot specify both ',' and '_'.")
    prec = -1
    if p < n and _rt.byte(spec, p) == 46:
        p += 1
        if p >= n or not digit(_rt.byte(spec, p)):
            raise ValueError("Format specifier missing precision")
        prec = 0
        while p < n and digit(_rt.byte(spec, p)):
            prec = prec * 10 + _rt.byte(spec, p) - 48
            p += 1
            if prec > 100000000:
                raise ValueError("Too many decimal digits in format string")
    if n - p > 1 and ulen(spec[p:]) > 1:
        raise ValueError(f"Invalid format specifier '{spec}' for object of type '{tyname(kind)}'")
    ty = ucode(spec, p) if p < n else -1  # -1: no type; an explicit NUL is 0
    if ty < 0 and kind == 3:
        ty = 115
    if ty < 0 and kind != 2:
        ty = 100
    if kind == 2 and ty < 0:
        ty = 0  # a float's default type is NUL, as in CPython
    if sep != 0 and ty != 0 and not known(ty, "defgEFG%") and not (sep == 95 and known(ty, "boxX")):
        raise ValueError(f"Cannot specify '{chr(sep)}' with '{tych(ty)}'.")
    body = ""
    pre = 0  # bytes of sign and prefix, before '=' padding
    if kind == 3:
        if ty != 115:
            raise ValueError(f"Unknown format code '{tych(ty)}' for object of type 'str'")
        if sign != 0:
            raise ValueError("Space not allowed in string format specifier" if sign == 32 else "Sign not allowed in string format specifier")
        if zneg:
            raise ValueError("Negative zero coercion (z) not allowed in string format specifier")
        if alt:
            raise ValueError("Alternate form (#) not allowed in string format specifier")
        if align == 61:
            raise ValueError("'=' alignment not allowed in string format specifier")
        body = sv[: uoff(sv, prec)] if prec >= 0 else sv
    elif (kind <= 1 or kind == 4) and known(ty, "bcdoxXn"):
        if prec >= 0:
            raise ValueError("Precision not allowed in integer format specifier")
        if zneg:
            raise ValueError("Negative zero coercion (z) not allowed in integer format specifier")
        if ty == 99 and kind == 4:
            raise OverflowError("Python int too large to convert to C long")
        if ty == 99:
            if sign != 0:
                raise ValueError("Sign not allowed with integer format specifier 'c'")
            if alt:
                raise ValueError("Alternate form (#) not allowed with integer format specifier 'c'")
            if iv < 0 or iv > 1114111:
                raise OverflowError("%c arg not in range(0x110000)")
            body = utf8(iv)
        else:
            base = 2 if ty == 98 else 8 if ty == 111 else 16 if ty == 120 or ty == 88 else 10
            digits = sv
            if kind != 4:
                hexd = "0123456789ABCDEF" if ty == 88 else "0123456789abcdef"
                u = _rt.wrap_sub(0, iv) if iv < 0 else iv  # |iv| as an unsigned 64-bit pattern
                nd = 0
                q = u
                while True:
                    nd += 1
                    q = _rt.udiv(q, base)
                    if q == 0:
                        break
                dg = _rt.str_new(nd)
                for i in range(nd):
                    _rt.str_put(dg, nd - 1 - i, _rt.byte(hexd, _rt.urem(u, base)))
                    u = _rt.udiv(u, base)
                digits = _rt.str_done(dg)
            head = "-" if iv < 0 else chr(sign) if sign == 43 or sign == 32 else ""
            if alt and base != 10:
                head = head + "0" + ("X" if ty == 88 else "x" if ty == 120 else chr(ty))
            pre = len(head)
            minw = width - pre if fill == "0" and align == 61 else 0
            body = head + group(digits, sep, 3 if base == 10 else 4, minw)
    else:
        # a float, or an int with a float type
        x = fv if kind == 2 else float(iv)
        if (ty != 0 or kind != 2) and not known(ty, "eEfFgGn%"):
            raise ValueError(f"Unknown format code '{tych(ty)}' for object of type '{tyname(kind)}'")
        neg = math.copysign(1.0, x) < 0.0 and not math.isnan(x)
        m = -x if neg else x
        t = pys_fmt_float(m, ty, prec, 1 if alt else 0)
        if zneg and neg and not math.isinf(m) and zero(t):
            neg = False  # z: no "-0" after rounding
        head = "-" if neg else chr(sign) if sign == 43 or sign == 32 else ""
        pre = len(head)
        ip = 0  # the integer digits
        while ip < len(t) and digit(_rt.byte(t, ip)):
            ip += 1
        minw = width - pre - (len(t) - ip) if fill == "0" and align == 61 else 0
        body = head + (group(t[:ip], sep, 3, minw) if ip > 0 else "0" * minw) + t[ip:]
    if align == 0:
        align = 62 if numeric else 60
    ln = ulen(body)
    if ln >= width:
        return body
    gap = width - ln
    f = len(fill)
    if gap > (9223372036854775807 - len(body)) // f:
        raise MemoryError
    # the result is built in place, with '=' padding after the sign and prefix (pre)
    left = 0 if align == 60 else gap // 2 if align == 94 else gap
    hd = pre if align == 61 else 0
    r = _rt.str_new(len(body) + gap * f)
    _rt.copy(r, 0, body, 0, hd)
    fillrun(r, hd, fill, left)
    _rt.copy(r, hd + left * f, body, hd, len(body) - hd)
    fillrun(r, left * f + len(body), fill, gap - left)
    return _rt.str_done(r)


def pys_format_str(s: str, spec: str) -> str:
    return fmt(3, 0, 0.0, s, spec)


def pys_format_int(v: int, isbool: int, spec: str) -> str:
    return fmt(1 if isbool != 0 else 0, v, 0.0, "", spec)


def pys_format_float(x: float, spec: str) -> str:
    return fmt(2, 0, x, "", spec)


def pys_format_bigdigits(neg: int, digits: str, spec: str) -> str:
    # an int past 64 bits (pys_big_format): its sign and its magnitude's digits
    return fmt(4, -1 if neg != 0 else 1, 0.0, digits, spec)


# ---------- bytes ----------
# A bytes object is a Str, its bytes a str's (see bytes in runtime.c), so its parameters here are
# strs. These are its operations: under names of their own where a str's does the same to the
# bytes (searches, replace of a non-empty old, a split at a separator), and apart where a bytes
# differs: its items are ints, its whitespace, case and digits are ASCII's, its widths count
# bytes, and replace() of an empty old puts new between bytes
def ascii_ws(c: int) -> bool:
    # a bytes's whitespace: space, \t, \n, \v, \f and \r
    return c == 32 or (c >= 9 and c <= 13)


def pys_bytes_has(b: str, x: int) -> int:
    # x in b, of an int x: a byte of b with that value
    if x < 0 or x > 255:
        raise ValueError("byte must be in range(0, 256)")
    for i in range(len(b)):
        if _rt.byte(b, i) == x:
            return 1
    return 0


def pys_bytes_contains(h: str, n: str) -> int:
    return pys_str_contains(h, n)


def pys_bytes_find(h: str, n: str, st: int, en: int) -> int:
    return pys_str_find(h, n, st, en)


def pys_bytes_rfind(h: str, n: str, st: int, en: int) -> int:
    return pys_str_rfind(h, n, st, en)


def pys_bytes_count(h: str, n: str, st: int, en: int) -> int:
    return pys_str_count(h, n, st, en)


def pys_bytes_index(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_find(h, n, st, en)
    if i < 0:
        raise ValueError("subsection not found")
    return i


def pys_bytes_rindex(h: str, n: str, st: int, en: int) -> int:
    i = pys_str_rfind(h, n, st, en)
    if i < 0:
        raise ValueError("subsection not found")
    return i


def pys_bytes_startswith(h: str, n: str, st: int, en: int) -> int:
    return pys_str_startswith(h, n, st, en)


def pys_bytes_endswith(h: str, n: str, st: int, en: int) -> int:
    return pys_str_endswith(h, n, st, en)


def pys_bytes_replace(s: str, a: str, b: str) -> str:
    return replaced(s, a, b, -1)


def pys_bytes_replace_count(s: str, a: str, b: str, n: int) -> str:
    return replaced(s, a, b, n)


def pys_bytes_partition(s: str, sep: str) -> tuple[str, str, str]:
    return pys_str_partition(s, sep)


def pys_bytes_rpartition(s: str, sep: str) -> tuple[str, str, str]:
    return pys_str_rpartition(s, sep)


def pys_bytes_removeprefix(s: str, p: str) -> str:
    return pys_str_removeprefix(s, p)


def pys_bytes_removesuffix(s: str, p: str) -> str:
    return pys_str_removesuffix(s, p)


def pys_bytes_join(sep: str, l: list[str]) -> str:
    for i in range(len(l)):
        if _rt.null(l[i]):
            # (an item of a list[bytes | None]: CPython's TypeError names a bytes-like object)
            raise TypeError("sequence item " + str(i) + ": expected a bytes-like object, NoneType found")
    return pys_str_join(sep, l)


def ws_split(s: str, maxsplit: int, right: bool) -> list[str]:
    # s.split() or s.rsplit() of a bytes, at runs of ASCII whitespace; past maxsplit parts (when
    # it is not negative) the rest is one part, its whitespace at the far end kept
    out: list[str] = []
    n = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if not right:
        i = 0
        while True:
            while i < n and ascii_ws(_rt.byte(s, i)):
                i += 1
            if i >= n:
                return out
            if left == 0:
                out.append(s[i:])
                return out
            left -= 1
            j = i
            while j < n and not ascii_ws(_rt.byte(s, j)):
                j += 1
            out.append(s[i:j])
            i = j
    j = n
    while True:
        while j > 0 and ascii_ws(_rt.byte(s, j - 1)):
            j -= 1
        if j <= 0:
            break
        if left == 0:
            out.append(s[:j])
            break
        left -= 1
        i = j
        while i > 0 and not ascii_ws(_rt.byte(s, i - 1)):
            i -= 1
        out.append(s[i:j])
        j = i
    out.reverse()
    return out


def pys_bytes_split(s: str, sep: str, maxsplit: int) -> list[str]:
    if _rt.null(sep):
        return ws_split(s, maxsplit, False)
    return pys_str_split(s, sep, maxsplit)


def pys_bytes_rsplit(s: str, sep: str, maxsplit: int) -> list[str]:
    if _rt.null(sep):
        return ws_split(s, maxsplit, True)
    return pys_str_rsplit(s, sep, maxsplit)


def bstrip(s: str, cs: str, m: int) -> str:
    # m: 1 left, 2 right, 3 both; the bytes of cs (ASCII whitespace where cs is null)
    i = 0
    j = len(s)
    if m & 1:
        while i < j and (ascii_ws(_rt.byte(s, i)) if _rt.null(cs) else _rt.find_byte(cs, _rt.byte(s, i), 0, len(cs)) >= 0):
            i += 1
    if m & 2:
        while j > i and (ascii_ws(_rt.byte(s, j - 1)) if _rt.null(cs) else _rt.find_byte(cs, _rt.byte(s, j - 1), 0, len(cs)) >= 0):
            j -= 1
    return s[i:j]


def pys_bytes_strip(s: str, cs: str) -> str:
    return bstrip(s, cs, 3)


def pys_bytes_lstrip(s: str, cs: str) -> str:
    return bstrip(s, cs, 1)


def pys_bytes_rstrip(s: str, cs: str) -> str:
    return bstrip(s, cs, 2)


def pys_bytes_upper(s: str) -> str:
    return mapcase(s, 1)


def pys_bytes_lower(s: str) -> str:
    return mapcase(s, 0)


def pys_bytes_swapcase(s: str) -> str:
    return mapcase(s, 2)


def pys_bytes_capitalize(s: str) -> str:
    r = _rt.str_new(len(s))
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (i == 0 and lowc(c)) or (i > 0 and upc(c)):
            c ^= 32
        _rt.str_put(r, i, c)
    return _rt.str_done(r)


def bclass(s: str, k: int) -> int:
    # every byte of s (and there is one) an ASCII letter (k 1), letter or digit (2), digit (0),
    # or whitespace (3)
    if len(s) == 0:
        return 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        ok = ascii_ws(c) if k == 3 else digit(c) or (k > 0 and (lowc(c) or upc(c))) if k == 2 else digit(c) if k == 0 else lowc(c) or upc(c)
        if not ok:
            return 0
    return 1


def pys_bytes_isalpha(s: str) -> int:
    return bclass(s, 1)


def pys_bytes_isalnum(s: str) -> int:
    return bclass(s, 2)


def pys_bytes_isdigit(s: str) -> int:
    return bclass(s, 0)


def pys_bytes_isspace(s: str) -> int:
    return bclass(s, 3)


def bcased(s: str, up: bool) -> int:
    # b.isupper() (up) or b.islower(): a cased ASCII letter, and none of the other case
    cased = False
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (lowc(c) and up) or (upc(c) and not up):
            return 0
        cased = cased or lowc(c) or upc(c)
    return 1 if cased else 0


def pys_bytes_isupper(s: str) -> int:
    return bcased(s, True)


def pys_bytes_islower(s: str) -> int:
    return bcased(s, False)


def pys_bytes_isascii(s: str) -> int:
    return pys_str_isascii(s)


def bpad(s: str, w: int, fill: str, how: int, name: str) -> str:
    # how: 0 right, 1 left, 2 center; widths count bytes; fill is null for a space, else one byte
    if not _rt.null(fill) and len(fill) != 1:
        raise TypeError(name + "() argument 2 must be a byte string of length 1, not bytes")
    c = 32 if _rt.null(fill) else _rt.byte(fill, 0)
    if len(s) >= w:
        return s
    gap = w - len(s)
    left = 0 if how == 1 else gap if how == 0 else gap // 2 + (gap & w & 1)  # CPython's centering
    r = _rt.str_new(w)
    for i in range(left):
        _rt.str_put(r, i, c)
    _rt.copy(r, left, s, 0, len(s))
    for i in range(left + len(s), w):
        _rt.str_put(r, i, c)
    return _rt.str_done(r)


def pys_bytes_ljust(s: str, w: int, fill: str) -> str:
    return bpad(s, w, fill, 1, "ljust")


def pys_bytes_rjust(s: str, w: int, fill: str) -> str:
    return bpad(s, w, fill, 0, "rjust")


def pys_bytes_center(s: str, w: int, fill: str) -> str:
    return bpad(s, w, fill, 2, "center")


def pys_bytes_zfill(s: str, w: int) -> str:
    if len(s) >= w:
        return s
    z = w - len(s)
    r = _rt.str_new(w)
    for i in range(z):
        _rt.str_put(r, i, 48)
    _rt.copy(r, z, s, 0, len(s))
    if len(s) > 0 and (_rt.byte(s, 0) == 43 or _rt.byte(s, 0) == 45):
        # a sign moves in front of the zeros
        _rt.str_put(r, 0, _rt.byte(s, 0))
        _rt.str_put(r, z, 48)
    return _rt.str_done(r)


def pys_bytes_splitlines(s: str, keep: int) -> list[str]:
    # the lines of a bytes end at \n, \r or \r\n only
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        j = i
        while j < n and _rt.byte(s, j) != 10 and _rt.byte(s, j) != 13:
            j += 1
        e = j
        if j < n:
            e = j + 2 if _rt.byte(s, j) == 13 and j + 1 < n and _rt.byte(s, j + 1) == 10 else j + 1
        out.append(s[i:e] if keep else s[i:j])
        i = e
    return out


def pys_bytes_hex(s: str) -> str:
    r = _rt.str_new(2 * len(s))
    for i in range(len(s)):
        c = _rt.byte(s, i)
        _rt.str_put(r, 2 * i, (48 if c >> 4 < 10 else 87) + (c >> 4))
        _rt.str_put(r, 2 * i + 1, (48 if c & 15 < 10 else 87) + (c & 15))
    return _rt.str_done(r)


def pys_bytes_hex_sep(s: str, sep: str, chars: int, per: int) -> str:
    # s.hex(sep, per) as CPython's (Python/pystrhex.c): sep (null: none), one ASCII character of a
    # str (chars 1) or byte of a bytes, between the groups of per bytes, which count from the
    # right where per is positive, from the left where it is negative (no groups where it is 0)
    if per > 2147483647 or per < -2147483648:
        raise OverflowError("Python int too large to convert to C int")  # (a C int argument)
    if _rt.null(sep):
        return pys_bytes_hex(s)
    k = len(sep)
    if chars == 1:
        k = 0
        i = 0
        while i < len(sep):
            i += u8seq(sep, i, len(sep))
            k += 1
    if k != 1:
        raise ValueError("sep must be length 1.")
    c = _rt.byte(sep, 0)
    if c > 127:
        raise ValueError("sep must be ASCII.")
    n = len(s)
    g = per if per >= 0 else -per
    r = _rt.str_new(2 * n + ((n - 1) // g if g > 0 and n > 0 else 0))
    j = 0
    for i in range(n):
        if g > 0 and i > 0 and ((per > 0 and (n - i) % g == 0) or (per < 0 and i % g == 0)):
            _rt.str_put(r, j, c)
            j += 1
        b = _rt.byte(s, i)
        _rt.str_put(r, j, (48 if b >> 4 < 10 else 87) + (b >> 4))
        _rt.str_put(r, j + 1, (48 if b & 15 < 10 else 87) + (b & 15))
        j += 2
    return _rt.str_done(r)


def pys_bytes_maketrans(frm: str, to: str) -> str:
    # bytes.maketrans(frm, to): the 256 bytes that map each byte of frm to the byte of to in its
    # place (the last, for a byte frm holds twice), and every other byte to itself
    if len(frm) != len(to):
        raise ValueError("maketrans arguments must have same length")
    r = _rt.str_new(256)
    for i in range(256):
        _rt.str_put(r, i, i)
    for i in range(len(frm)):
        _rt.str_put(r, _rt.byte(frm, i), _rt.byte(to, i))
    return _rt.str_done(r)


def pys_bytes_translate(s: str, table: str, delete: str) -> str:
    # s.translate(table, delete): the bytes of s that delete (null: b"") does not hold, each
    # mapped by table, 256 bytes (null: None, which maps none)
    if not _rt.null(table) and len(table) != 256:
        raise ValueError("translation table must be 256 characters long")
    n = len(s)
    keep = n
    if not _rt.null(delete) and len(delete) > 0:
        keep = 0
        for i in range(n):
            if _rt.find_byte(delete, _rt.byte(s, i), 0, len(delete)) < 0:
                keep += 1
    r = _rt.str_new(keep)
    j = 0
    for i in range(n):
        c = _rt.byte(s, i)
        if keep < n and _rt.find_byte(delete, c, 0, len(delete)) >= 0:
            continue
        _rt.str_put(r, j, c if _rt.null(table) else _rt.byte(table, c))
        j += 1
    return _rt.str_done(r)


def hexval(c: int) -> int:
    return c - 48 if digit(c) else c - 87 if c >= 97 and c <= 102 else c - 55 if c >= 65 and c <= 70 else -1


def pys_bytes_fromhex(s: str) -> str:
    # bytes.fromhex(s): pairs of hexadecimal digits, ASCII whitespace between them
    out: list[int] = []
    i = 0
    n = len(s)
    while True:
        while i < n and ascii_ws(_rt.byte(s, i)):
            i += 1
        if i >= n:
            break
        hi = hexval(_rt.byte(s, i))
        lo = hexval(_rt.byte(s, i + 1)) if i + 1 < n else -1
        if hi < 0 or lo < 0:
            raise ValueError("non-hexadecimal number found in fromhex() arg at position " + str(i if hi < 0 else i + 1))
        out.append(hi * 16 + lo)
        i += 2
    return pys_bytes_from_list(out)


def pys_bytes_from_list(xs: list[int]) -> str:
    # bytes(xs) of a list of ints. Each item's low byte is stored and the items' bits are
    # gathered, so the range is tested once, after a loop that has no exit: an int below 0 or
    # above 255 leaves a bit outside the low eight. The error is CPython's whichever item is
    # the first out of range, and nothing sees the bytes of a list that has one
    n = len(xs)
    r = _rt.str_new(n)
    bits = 0
    for i in range(n):
        x = xs[i]
        bits |= x
        _rt.str_put(r, i, x & 255)
    if bits < 0 or bits > 255:
        raise ValueError("bytes must be in range(0, 256)")
    return _rt.str_done(r)


def pys_bytes_zeros(n: int) -> str:
    # bytes(n): n zero bytes
    if n < 0:
        raise ValueError("negative count")
    return _rt.str_done(_rt.str_new(n))


# ---- codecs: str.encode() and bytes.decode() with CPython's UTF-8, Latin-1 and ASCII codecs
# and error handlers. A str holds UTF-8, where a surrogate is its three bytes (ED A0 80 to ED BF
# BF, which decode with "surrogateescape" or "surrogatepass" makes)
def codec_of(encoding: str) -> int:
    # the codec an encoding names, as codecs.lookup() finds it among encodings.aliases: 0 UTF-8,
    # 1 Latin-1, 2 ASCII, else CPython's LookupError. The name is normalized as
    # encodings.normalize_encoding does: lower case, other characters than letters, digits and
    # '.' one '_' between the parts
    norm = ""
    punct = False
    for i in range(len(encoding)):
        c = _rt.byte(encoding, i)
        if digit(c) or lowc(c) or upc(c) or c == 46:
            if punct and len(norm) > 0:
                norm += "_"
            norm += chr(c | 32 if upc(c) else c)
            punct = False
        else:
            punct = True
    alias = norm.replace(".", "_")
    for nm in [norm, alias]:
        if nm in ["utf_8", "cp65001", "u8", "utf", "utf8", "utf8_ucs2", "utf8_ucs4"]:
            return 0
        if nm in ["latin_1", "8859", "cp819", "csisolatin1", "ibm819", "iso8859", "iso8859_1", "iso_8859_1",
                  "iso_8859_1_1987", "iso_ir_100", "l1", "latin", "latin1"]:
            return 1
        if nm in ["ascii", "646", "ansi_x3.4_1968", "ansi_x3.4_1986", "ansi_x3_4_1968", "cp367", "csascii",
                  "ibm367", "iso646_us", "iso_646.irv_1991", "iso_ir_6", "us", "us_ascii"]:
            return 2
    raise LookupError("unknown encoding: " + encoding)


def codec_name(k: int) -> str:
    return "utf-8" if k == 0 else "latin-1" if k == 1 else "ascii"


def u8seq(s: str, i: int, n: int) -> int:
    # the length of the UTF-8 character at s[i] (a surrogate's three bytes are one), as a str
    # holds it and runtime.c's u8char counts it; 1 for a byte that begins none, which an
    # overlong sequence's first byte and one past U+10FFFF's do (#1587)
    c = _rt.byte(s, i)
    if c < 0xC2 or c > 0xF4:
        return 1
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    if i + k > n:
        return 1
    for j in range(i + 1, i + k):
        if _rt.byte(s, j) & 0xC0 != 0x80:
            return 1
    c2 = _rt.byte(s, i + 1)
    if (c == 0xE0 and c2 < 0xA0) or (c == 0xF0 and c2 < 0x90) or (c == 0xF4 and c2 >= 0x90):
        return 1
    return k


def u8cp(s: str, i: int, k: int) -> int:
    # the code point of the k bytes of UTF-8 at s[i] (k 1: the byte)
    if k == 1:
        return _rt.byte(s, i)
    v = _rt.byte(s, i) & (0x1F if k == 2 else 0x0F if k == 3 else 0x07)
    for j in range(i + 1, i + k):
        v = (v << 6) | (_rt.byte(s, j) & 0x3F)
    return v


def u8put(out: list[str], cp: int) -> None:
    # the UTF-8 bytes of code point cp (a surrogate's too), each as chr() writes a byte
    if cp < 0x80:
        out.append(chr(cp))
    elif cp < 0x800:
        out.append(chr(0xC0 | (cp >> 6)) + chr(0x80 | (cp & 0x3F)))
    elif cp < 0x10000:
        out.append(chr(0xE0 | (cp >> 12)) + chr(0x80 | ((cp >> 6) & 0x3F)) + chr(0x80 | (cp & 0x3F)))
    else:
        out.append(chr(0xF0 | (cp >> 18)) + chr(0x80 | ((cp >> 12) & 0x3F)) + chr(0x80 | ((cp >> 6) & 0x3F)) + chr(0x80 | (cp & 0x3F)))


def hexpart(v: int, n: int) -> str:
    # v as n lower-case hexadecimal digits
    r = _rt.str_new(n)
    for i in range(n):
        d = (v >> (4 * (n - 1 - i))) & 15
        _rt.str_put(r, i, (48 if d < 10 else 87) + d)
    return _rt.str_done(r)


def escaped(cp: int) -> str:
    # \xNN, \uNNNN or \UNNNNNNNN, as CPython's UnicodeEncodeError message and "backslashreplace"
    # write a code point
    return "\\x" + hexpart(cp, 2) if cp < 0x100 else "\\u" + hexpart(cp, 4) if cp < 0x10000 else "\\U" + hexpart(cp, 8)


def pys_str_encode(s: str, encoding: str, errors: str) -> str:
    # s.encode(encoding, errors): the bytes; the characters the codec cannot encode (a surrogate
    # in UTF-8, above U+00FF or U+007F) go to the error handler in runs, as CPython gives them.
    # An omitted (null) encoding is UTF-8, omitted errors "strict"
    k = 0 if _rt.null(encoding) else codec_of(encoding)
    if _rt.null(errors):
        errors = "strict"
    if pys_str_isascii(s) == 1 or (k == 0 and _rt.find_byte(s, 0xED, 0, len(s)) < 0):
        return s  # (only ED begins a surrogate's bytes)
    limit = 0x80 if k == 2 else 0x100 if k == 1 else 0x110000
    out: list[str] = []
    n = len(s)
    i = 0
    start = 0
    pos = 0  # out holds the bytes of s[:start]; s[:i] holds pos characters
    while i < n:
        m = u8seq(s, i, n)
        cp = u8cp(s, i, m)
        surr = cp >= 0xD800 and cp <= 0xDFFF and m == 3
        if cp < 0x80 or (k == 0 and not surr):
            i += m
            pos += 1
            continue
        out.append(s[start:i])
        if cp < limit and not surr:
            out.append(chr(cp))  # (Latin-1: the byte)
            i += m
            pos += 1
            start = i
            continue
        first = pos
        cps: list[int] = []
        while i < n:
            m = u8seq(s, i, n)
            cp = u8cp(s, i, m)
            surr = cp >= 0xD800 and cp <= 0xDFFF and m == 3
            if cp < limit and not surr:
                break
            cps.append(cp)
            i += m
            pos += 1
        out.append(encode_error(cps, first, k, errors))
        start = i
    out.append(s[start:])
    return "".join(out)


def pys_unicode_error_str(dec: int, encoding: str, obj: str, start: int, end: int, reason: str) -> str:
    # str() of UnicodeDecodeError(encoding, obj, start, end, reason) (dec 1: obj a bytes) or of
    # UnicodeEncodeError(...) (obj a str, whose characters start and end count), as CPython's
    # (Objects/exceptions.c): the one byte or character at start, or the range to end
    n = len(obj)
    if dec == 1:
        if start >= 0 and start < n and end >= 0 and end <= n and end == start + 1:
            return "'" + encoding + "' codec can't decode byte 0x" + hexpart(_rt.byte(obj, start), 2) + " in position " + str(start) + ": " + reason
        return "'" + encoding + "' codec can't decode bytes in position " + str(start) + "-" + str(end - 1) + ": " + reason
    i = 0
    chars = 0
    bad = 0
    while i < n:
        m = u8seq(obj, i, n)
        if chars == start:
            bad = u8cp(obj, i, m)
        i += m
        chars += 1
    if start >= 0 and start < chars and end >= 0 and end <= chars and end == start + 1:
        return "'" + encoding + "' codec can't encode character '" + escaped(bad) + "' in position " + str(start) + ": " + reason
    return "'" + encoding + "' codec can't encode characters in position " + str(start) + "-" + str(end - 1) + ": " + reason


def encode_error(cps: list[int], pos: int, k: int, errors: str) -> str:
    # the bytes error handler errors makes of code points cps, from character pos of the str on,
    # which codec k cannot encode, as CPython's handlers make them
    if errors == "replace":
        return "?" * len(cps)
    if errors == "ignore":
        return ""
    out: list[str] = []
    if errors == "backslashreplace":
        for cp in cps:
            out.append(escaped(cp))
        return "".join(out)
    if errors == "xmlcharrefreplace":
        for cp in cps:
            out.append("&#" + str(cp) + ";")
        return "".join(out)
    j = 0
    if errors == "surrogateescape":
        while j < len(cps) and cps[j] >= 0xDC80 and cps[j] <= 0xDCFF:
            j += 1
        if j == len(cps):
            for cp in cps:
                out.append(chr(cp - 0xDC00))
            return "".join(out)
    elif errors == "surrogatepass" and k == 0:
        for cp in cps:
            u8put(out, cp)
        return "".join(out)
    elif errors != "strict" and errors != "surrogatepass":
        raise LookupError("unknown error handler name '" + errors + "'")
    start = pos + j
    end = pos + len(cps)
    reason = "surrogates not allowed" if k == 0 else "ordinal not in range(256)" if k == 1 else "ordinal not in range(128)"
    if end - start == 1:
        _rt.fail("UnicodeEncodeError", "'" + codec_name(k) + "' codec can't encode character '" + escaped(cps[j]) + "' in position " + str(start) + ": " + reason)
    _rt.fail("UnicodeEncodeError", "'" + codec_name(k) + "' codec can't encode characters in position " + str(start) + "-" + str(end - 1) + ": " + reason)
    return ""


def u8char(b: str, i: int, n: int) -> int:
    # the length of the UTF-8 character at b[i], as CPython's decoder reads it (stringlib's
    # utf8_decode), or 0 where the bytes from i on are none (u8bad tells why, and how many)
    c = _rt.byte(b, i)
    if c < 0xC2 or c > 0xF4:
        return 0
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    lo = 0xA0 if c == 0xE0 else 0x90 if c == 0xF0 else 0x80
    hi = 0x9F if c == 0xED else 0x8F if c == 0xF4 else 0xBF
    for j in range(i + 1, i + k):
        if j >= n:
            return 0
        d = _rt.byte(b, j)
        if d < lo or d > hi:
            return 0
        lo = 0x80
        hi = 0xBF
    return k


def u8bad(b: str, i: int, n: int) -> int:
    # where the bytes from b[i] on that are no character end (u8char 0), as CPython's decoder
    # gives them to the error handler; minus that end where the data ends first
    c = _rt.byte(b, i)
    if c < 0xC2 or c > 0xF4:
        return i + 1  # (invalid start byte)
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    lo = 0xA0 if c == 0xE0 else 0x90 if c == 0xF0 else 0x80
    hi = 0x9F if c == 0xED else 0x8F if c == 0xF4 else 0xBF
    for j in range(i + 1, i + k):
        if j >= n:
            return -n  # (unexpected end of data)
        d = _rt.byte(b, j)
        if d < lo or d > hi:
            return j  # (invalid continuation byte)
        lo = 0x80
        hi = 0xBF
    return i + k


def pys_bytes_decode(b: str, encoding: str, errors: str) -> str:
    # b.decode(encoding, errors): the str; the bytes the codec cannot decode go to the error
    # handler as CPython's decoder gives them (an omitted encoding is UTF-8, as in encode). An
    # empty b is the empty str whatever its encoding names: CPython looks no codec up for it
    if len(b) == 0:
        return b
    k = 0 if _rt.null(encoding) else codec_of(encoding)
    if _rt.null(errors):
        errors = "strict"
    if pys_str_isascii(b) == 1:
        return b
    out: list[str] = []
    n = len(b)
    i = 0
    start = 0  # out holds the characters of b[:start]
    while i < n:
        c = _rt.byte(b, i)
        if c < 0x80:
            i += 1
            continue
        if k == 1:
            out.append(b[start:i])
            u8put(out, c)
            i += 1
            start = i
            continue
        m = u8char(b, i, n) if k == 0 else 0
        if m > 0:
            i += m  # (its bytes are the str's)
            continue
        end = u8bad(b, i, n) if k == 0 else i + 1
        why = "ordinal not in range(128)" if k == 2 else "invalid start byte" if end == i + 1 and (c < 0xC2 or c > 0xF4) else "unexpected end of data" if end < 0 else "invalid continuation byte"
        end = -end if end < 0 else end
        out.append(b[start:i])
        rep = decode_error(b, i, end, k, errors, why)
        out.append(rep[0])
        i = rep[1]
        start = i
    out.append(b[start:])
    return "".join(out)


def decode_error(b: str, start: int, end: int, k: int, errors: str, why: str) -> tuple[str, int]:
    # what error handler errors makes of the bytes b[start:end], which codec k cannot decode (for
    # why), and where decoding goes on, as CPython's handlers do
    out: list[str] = []
    if errors == "replace":
        u8put(out, 0xFFFD)
        return ("".join(out), end)
    if errors == "ignore":
        return ("", end)
    if errors == "backslashreplace":
        for j in range(start, end):
            out.append("\\x" + hexpart(_rt.byte(b, j), 2))
        return ("".join(out), end)
    if errors == "surrogateescape":
        for j in range(start, end):
            u8put(out, 0xDC00 + _rt.byte(b, j))
        return ("".join(out), end)
    if errors == "surrogatepass" and k == 0 and len(b) - start >= 3:
        b1 = _rt.byte(b, start)
        b2 = _rt.byte(b, start + 1)
        b3 = _rt.byte(b, start + 2)
        cp = ((b1 & 0x0F) << 12) | ((b2 & 0x3F) << 6) | (b3 & 0x3F)
        if b1 & 0xF0 == 0xE0 and b2 & 0xC0 == 0x80 and b3 & 0xC0 == 0x80 and cp >= 0xD800 and cp <= 0xDFFF:
            return (b[start : start + 3], start + 3)  # (a surrogate's three bytes, as a str holds it)
    if errors == "xmlcharrefreplace" or errors == "namereplace":
        raise TypeError("don't know how to handle UnicodeDecodeError in error callback")
    if errors != "strict" and errors != "surrogatepass":
        raise LookupError("unknown error handler name '" + errors + "'")
    if end - start == 1:
        _rt.fail("UnicodeDecodeError", "'" + codec_name(k) + "' codec can't decode byte 0x" + hexpart(_rt.byte(b, start), 2) + " in position " + str(start) + ": " + why)
    _rt.fail("UnicodeDecodeError", "'" + codec_name(k) + "' codec can't decode bytes in position " + str(start) + "-" + str(end - 1) + ": " + why)
    return ("", end)


# ---------- lists: the header and its item array (runtime.c's List) ----------
# The layout, the inline items of a short scanned list, the sentinels of an emptied list and the
# kinds of item arrays are described with runtime.c's lists. This code reads and writes the
# header through its fields (_rt.get, _rt.set) and the items as words (_rt.word, _rt.put), which
# nothing checks: an index it passes is one it has tested. A list's identity or promoting-int
# companion (ids) exists only in a program that opts in to one, which pys_rt_opt_in() tells, as
# runtime.c's opt_in() does: a plain AOT program's build drops what follows that test. The test
# is written out where it is made (ids is not null, and the program opts in), as runtime.c
# writes l->ids && opt_in(): LLVM then branches on it as it did there.


def pys_alloc(n: int) -> _rt.Ptr: ...
def pys_alloc_atomic(n: int) -> _rt.Ptr: ...
def pys_rt_oom() -> None: ...
def pys_rt_opt_in() -> int: ...
def pys_rt_empty_list() -> _rt.Ptr: ...
def pys_rt_empty_atomic() -> _rt.Ptr: ...
def pys_rt_empty_inline() -> _rt.Ptr: ...
def pys_rt_empty_identity(kind: int) -> _rt.Ptr: ...
def pys_rt_atomic_items(a: _rt.Ptr) -> int: ...
def pys_rt_list_box(value: int, kind: int) -> int: ...
def pys_rt_big_list(l: _rt.Ptr) -> int: ...
def pys_list_identity(l: _rt.Ptr, kind: int) -> None: ...


@_rt.unchecked
def list_inline(l: _rt.Ptr) -> _rt.Ptr:
    # the items that a scanned list of at most 4 keeps in its header's own object, after the header
    return _rt.offset(l, _rt.sizeof("List"))


@_rt.unchecked
def pys_list_empty(l: _rt.Ptr) -> None:
    # detach an empty list's historical storage without allocating: it keeps the kind of its
    # items in the sentinel it is left with (cap 0 during a sort: that marker stays)
    if _rt.get(l, "List.cap") != 0:
        a = _rt.getp(l, "List.a")
        if a is list_inline(l):
            _rt.setp(l, "List.a", pys_rt_empty_inline())  # (whoever removed its items cleared their slots)
        elif pys_rt_atomic_items(a) != 0:
            _rt.setp(l, "List.a", pys_rt_empty_atomic())
        else:
            _rt.setp(l, "List.a", pys_rt_empty_list())
        _rt.set(l, "List.cap", 0)
        if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
            _rt.setp(l, "List.ids", pys_rt_empty_identity(_rt.word(_rt.getp(l, "List.ids"), 0)))


@_rt.unchecked
def item_array(n: int, atomic: int) -> _rt.Ptr:
    # an array of n items, of the kind asked for: atomic ones are never scanned
    return pys_alloc_atomic(n * 8) if atomic != 0 else pys_alloc(n * 8)


@_rt.unchecked
def pys_list_make(cap: int, atomic: int) -> _rt.Ptr:
    # a new empty list with room for cap items, at least 4: scanned ones of at most 4 inline
    if atomic == 0 and cap <= 4:
        # (64 bytes: the allocator's slack byte falls in the 72-byte class's last 8)
        l = pys_alloc(_rt.sizeof("List") + 32)
        _rt.set(l, "List.cap", 4)
        _rt.setp(l, "List.a", list_inline(l))
        return l
    # (the allocator adds one slack byte: the whole header, without the next size class)
    l = pys_alloc(_rt.sizeof("List") - 1)
    c = cap if cap > 4 else 4
    _rt.set(l, "List.cap", c)
    _rt.setp(l, "List.a", item_array(c, atomic))
    return l


def pys_list_new(cap: int) -> _rt.Ptr:
    return pys_list_make(cap, 0)


def pys_list_new_atomic(cap: int) -> _rt.Ptr:
    # a list[int], list[float] or list[bool]: its items are never scanned
    return pys_list_make(cap, 1)


@_rt.unchecked
def pys_list_from_const(values: _rt.Ptr, n: int) -> _rt.Ptr:
    # a large scalar literal: one copy of immutable pointer-free slots into a fresh atomic array
    if _rt.ult(1152921504606846975, n):
        pys_rt_oom()
    l = pys_list_make(n, 1)
    if n != 0:
        _rt.cpy(_rt.getp(l, "List.a"), values, n * 8)
    _rt.set(l, "List.len", n)
    return l


@_rt.unchecked
def pys_list_reserve(l: _rt.Ptr, n: int) -> None:
    # room for n items: twice the capacity at least, in an array of the kind of the one it copies.
    # (Here and below a field is read again after a call, as runtime.c reads it: a value kept in
    # a local across a call that is rarely made costs the common path a register to save)
    if n <= _rt.get(l, "List.cap"):
        return
    c = _rt.get(l, "List.cap") * 2 if _rt.get(l, "List.cap") * 2 > n else n
    if c < 4:
        c = 4
    a = _rt.nil()
    if _rt.getp(l, "List.a") is pys_rt_empty_inline() and c == 4:
        a = list_inline(l)  # (emptied, and its items fit inline again)
    else:
        a = item_array(c, pys_rt_atomic_items(_rt.getp(l, "List.a")))
        _rt.cpy(a, _rt.getp(l, "List.a"), _rt.get(l, "List.len") * 8)
        if _rt.getp(l, "List.a") is list_inline(l):
            _rt.fill(_rt.getp(l, "List.a"), 0, 32)  # (moved: the header keeps none of them)
    _rt.setp(l, "List.a", a)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        if c > 1152921504606846974:
            pys_rt_oom()
        ids = pys_alloc((c + 1) * 8)
        _rt.cpy(ids, _rt.getp(l, "List.ids"), (_rt.get(l, "List.len") + 1) * 8)
        _rt.setp(l, "List.ids", ids)
    _rt.set(l, "List.cap", c)


@_rt.cold
@_rt.unchecked
def list_append_boxed(l: _rt.Ptr, v: int) -> None:
    # append to a list with a companion: the item's box first, as it may allocate
    box = pys_rt_list_box(v, _rt.word(_rt.getp(l, "List.ids"), 0))
    if _rt.get(l, "List.len") == _rt.get(l, "List.cap"):
        pys_list_reserve(l, _rt.get(l, "List.len") + 1)
    n = _rt.get(l, "List.len")
    _rt.put(_rt.getp(l, "List.ids"), n + 1, box)
    _rt.put(_rt.getp(l, "List.a"), n, v)
    _rt.set(l, "List.len", n + 1)


@_rt.unchecked
def pys_list_append(l: _rt.Ptr, v: int) -> None:
    # (the ordinary append stays small enough for LLVM to inline, also in a program that opts in)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        list_append_boxed(l, v)
        return
    if _rt.get(l, "List.len") == _rt.get(l, "List.cap"):
        pys_list_reserve(l, _rt.get(l, "List.len") + 1)
    n = _rt.get(l, "List.len")
    _rt.set(l, "List.len", n + 1)
    _rt.put(_rt.getp(l, "List.a"), n, v)


@_rt.unchecked
def pys_list_get(l: _rt.Ptr, i: int) -> int:
    n = _rt.get(l, "List.len")
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError("list index out of range")
    return _rt.word(_rt.getp(l, "List.a"), i)


@_rt.unchecked
def pys_list_set(l: _rt.Ptr, i: int, v: int) -> None:
    n = _rt.get(l, "List.len")
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError("list assignment index out of range")
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        # (a pending fresh identity, without an allocation; an int that fits has no entry)
        _rt.put(_rt.getp(l, "List.ids"), i + 1, 0)
        if pys_rt_big_list(l) == 0:
            _rt.put(_rt.getp(l, "List.ids"), 0, _rt.word(_rt.getp(l, "List.ids"), 0) | 4)
    _rt.put(_rt.getp(l, "List.a"), i, v)


@_rt.unchecked
def pys_list_pop(l: _rt.Ptr, i: int) -> int:
    # (a slot a list no longer uses is zeroed: the collector scans the whole array, so a stale
    # pointer there would keep the removed item alive, and a removed file open)
    if _rt.get(l, "List.len") == 0:
        raise IndexError("pop from empty list")
    n = _rt.get(l, "List.len")
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError("pop index out of range")
    v = _rt.word(_rt.getp(l, "List.a"), i)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        ids = _rt.getp(l, "List.ids")
        _rt.move(_rt.at(ids, i + 1), _rt.at(ids, i + 2), (_rt.get(l, "List.len") - i - 1) * 8)
        _rt.put(_rt.getp(l, "List.ids"), _rt.get(l, "List.len"), 0)
    _rt.move(_rt.at(_rt.getp(l, "List.a"), i), _rt.at(_rt.getp(l, "List.a"), i + 1), (_rt.get(l, "List.len") - i - 1) * 8)
    n = _rt.get(l, "List.len") - 1
    _rt.set(l, "List.len", n)
    _rt.put(_rt.getp(l, "List.a"), n, 0)
    if _rt.get(l, "List.len") == 0:
        pys_list_empty(l)
    return v


@_rt.unchecked
def pys_list_del(l: _rt.Ptr, i: int) -> None:
    n = _rt.get(l, "List.len")
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError("list assignment index out of range")
    pys_list_pop(l, i)


@_rt.unchecked
def pys_list_insert(l: _rt.Ptr, i: int, v: int) -> None:
    if i < 0:
        i += _rt.get(l, "List.len")
        if i < 0:
            i = 0
    if i > _rt.get(l, "List.len"):
        i = _rt.get(l, "List.len")
    box = pys_rt_list_box(v, _rt.word(_rt.getp(l, "List.ids"), 0)) if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0 else 0
    pys_list_reserve(l, _rt.get(l, "List.len") + 1)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        ids = _rt.getp(l, "List.ids")
        _rt.move(_rt.at(ids, i + 2), _rt.at(ids, i + 1), (_rt.get(l, "List.len") - i) * 8)
        _rt.put(_rt.getp(l, "List.ids"), i + 1, box)
    _rt.move(_rt.at(_rt.getp(l, "List.a"), i + 1), _rt.at(_rt.getp(l, "List.a"), i), (_rt.get(l, "List.len") - i) * 8)
    _rt.put(_rt.getp(l, "List.a"), i, v)
    _rt.set(l, "List.len", _rt.get(l, "List.len") + 1)


@_rt.unchecked
def pys_list_extend(l: _rt.Ptr, m: _rt.Ptr) -> None:
    identity_pair(l, m)
    n = _rt.get(m, "List.len")
    pys_list_reserve(l, _rt.get(l, "List.len") + n)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        ids = _rt.at(_rt.getp(l, "List.ids"), _rt.get(l, "List.len") + 1)
        if _rt.null(_rt.getp(m, "List.ids")):
            _rt.fill(ids, 0, n * 8)  # (m's ints fit)
        else:
            _rt.cpy(ids, _rt.at(_rt.getp(m, "List.ids"), 1), n * 8)
    _rt.cpy(_rt.at(_rt.getp(l, "List.a"), _rt.get(l, "List.len")), _rt.getp(m, "List.a"), n * 8)
    _rt.set(l, "List.len", _rt.get(l, "List.len") + n)


@_rt.unchecked
def span_lo(lo: int, n: int) -> int:
    # a slice's lower bound within 0..n (-2**63: omitted), and span_hi its upper one
    if lo == -9223372036854775807 - 1:
        return 0
    if lo < 0:
        lo += n
        return 0 if lo < 0 else lo
    return n if lo > n else lo


@_rt.unchecked
def span_hi(hi: int, n: int) -> int:
    if hi == -9223372036854775807 - 1:
        return n
    if hi < 0:
        hi += n
        return 0 if hi < 0 else hi
    return n if hi > n else hi


@_rt.unchecked
def pys_list_slice(l: _rt.Ptr, lo: int, hi: int) -> _rt.Ptr:
    n = _rt.get(l, "List.len")
    lo = span_lo(lo, n)
    hi = span_hi(hi, n)
    if hi < lo:
        hi = lo
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))
    r = pys_list_make(hi - lo, pys_rt_atomic_items(_rt.getp(l, "List.a")))
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        ids = _rt.getp(l, "List.ids")
        pys_list_identity(r, _rt.word(ids, 0))
        _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(ids, lo + 1), (hi - lo) * 8)
    _rt.cpy(_rt.getp(r, "List.a"), _rt.at(_rt.getp(l, "List.a"), lo), (hi - lo) * 8)
    _rt.set(r, "List.len", hi - lo)
    return r


def pys_list_copy(l: _rt.Ptr) -> _rt.Ptr:
    return pys_list_slice(l, -9223372036854775807 - 1, -9223372036854775807 - 1)


@_rt.unchecked
def pys_list_clear(l: _rt.Ptr) -> None:
    n = _rt.get(l, "List.len")
    _rt.fill(_rt.getp(l, "List.a"), 0, n * 8)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        _rt.fill(_rt.at(_rt.getp(l, "List.ids"), 1), 0, n * 8)
    _rt.set(l, "List.len", 0)
    pys_list_empty(l)


@_rt.unchecked
def slice_step(st: int) -> int:
    # a slice's step, as CPython's PySlice_AdjustIndices takes it; slice_lo and slice_count then
    # give the first index and the number of items of [lo:hi:st] in a sequence of m (-2**63: omitted)
    if st == 0:
        raise ValueError("slice step cannot be zero")
    return -9223372036854775807 if st < -9223372036854775807 else st


@_rt.unchecked
def slice_lo(lo: int, st: int, m: int) -> int:
    if lo == -9223372036854775807 - 1:
        return m - 1 if st < 0 else 0
    if lo < 0:
        lo += m
        if lo < 0:
            return -1 if st < 0 else 0
        return lo
    if lo >= m:
        return m - 1 if st < 0 else m
    return lo


@_rt.unchecked
def slice_count(lo: int, hi: int, st: int, m: int) -> int:
    if hi == -9223372036854775807 - 1:
        hi = -1 if st < 0 else m
    elif hi < 0:
        hi += m
        if hi < 0:
            hi = -1 if st < 0 else 0
    elif hi >= m:
        hi = m - 1 if st < 0 else m
    if st < 0:
        return _rt.udiv(lo - hi - 1, -st) + 1 if hi < lo else 0
    return _rt.udiv(hi - lo - 1, st) + 1 if lo < hi else 0


@_rt.unchecked
def pys_list_slice_step(l: _rt.Ptr, lo: int, hi: int, st: int) -> _rt.Ptr:
    st = slice_step(st)
    lo = slice_lo(lo, st, _rt.get(l, "List.len"))
    n = slice_count(lo, hi, st, _rt.get(l, "List.len"))
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))
    r = pys_list_make(n, pys_rt_atomic_items(_rt.getp(l, "List.a")))
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(r, _rt.word(_rt.getp(l, "List.ids"), 0))
    for i in range(n):
        _rt.put(_rt.getp(r, "List.a"), i, _rt.word(_rt.getp(l, "List.a"), lo + i * st))
        if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
            _rt.put(_rt.getp(r, "List.ids"), i + 1, _rt.word(_rt.getp(l, "List.ids"), lo + i * st + 1))
    _rt.set(r, "List.len", n)
    return r


@_rt.unchecked
def pys_list_set_slice(l: _rt.Ptr, lo: int, hi: int, st: int, v: _rt.Ptr) -> None:
    # l[lo:hi:st] = v: a stepped slice takes as many items as it has; a plain one moves the
    # items after it by the difference, and zeroes the slots that the list no longer uses
    n = _rt.get(l, "List.len")
    st = slice_step(st)
    lo = slice_lo(lo, st, n)
    k = slice_count(lo, hi, st, n)
    m = _rt.get(v, "List.len")
    if v is l:
        v = pys_list_copy(l)
    identity_pair(l, v)
    if st != 1:
        if m != k:
            raise ValueError("attempt to assign sequence of size " + str(m) + " to extended slice of size " + str(k))
        for i in range(k):
            _rt.put(_rt.getp(l, "List.a"), lo + i * st, _rt.word(_rt.getp(v, "List.a"), i))
            if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
                # (v's ints fit where it has no companion)
                box = 0 if _rt.null(_rt.getp(v, "List.ids")) else _rt.word(_rt.getp(v, "List.ids"), i + 1)
                _rt.put(_rt.getp(l, "List.ids"), lo + i * st + 1, box)
        return
    if n + m - k == 0:
        pys_list_clear(l)
        return
    if m > k:
        pys_list_reserve(l, n + m - k)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        ids = _rt.getp(l, "List.ids")
        _rt.move(_rt.at(ids, lo + m + 1), _rt.at(ids, lo + k + 1), (n - lo - k) * 8)
        if m < k:
            _rt.fill(_rt.at(ids, n + m - k + 1), 0, (k - m) * 8)
        if _rt.null(_rt.getp(v, "List.ids")):
            _rt.fill(_rt.at(ids, lo + 1), 0, m * 8)
        else:
            _rt.cpy(_rt.at(ids, lo + 1), _rt.at(_rt.getp(v, "List.ids"), 1), m * 8)
    a = _rt.getp(l, "List.a")
    _rt.move(_rt.at(a, lo + m), _rt.at(a, lo + k), (n - lo - k) * 8)
    if m < k:
        _rt.fill(_rt.at(a, n + m - k), 0, (k - m) * 8)
    _rt.cpy(_rt.at(a, lo), _rt.getp(v, "List.a"), m * 8)
    _rt.set(l, "List.len", n + m - k)


@_rt.unchecked
def pys_list_del_slice(l: _rt.Ptr, lo: int, hi: int, st: int) -> None:
    n = _rt.get(l, "List.len")
    st = slice_step(st)
    lo = slice_lo(lo, st, n)
    k = slice_count(lo, hi, st, n)
    w = n - k
    a = _rt.getp(l, "List.a")
    if st == 1:
        _rt.move(_rt.at(a, lo), _rt.at(a, lo + k), (n - lo - k) * 8)
        if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
            _rt.move(_rt.at(_rt.getp(l, "List.ids"), lo + 1), _rt.at(_rt.getp(l, "List.ids"), lo + k + 1), (n - lo - k) * 8)
    elif k != 0:
        if st < 0:
            lo += st * (k - 1)  # (the same items, first to last)
            st = -st
        w = lo
        j = 0
        i = lo
        while i < n:
            if j < k and i == lo + j * st:
                j += 1
            else:
                _rt.put(a, w, _rt.word(a, i))
                if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
                    _rt.put(_rt.getp(l, "List.ids"), w + 1, _rt.word(_rt.getp(l, "List.ids"), i + 1))
                w += 1
            i += 1
    _rt.fill(_rt.at(a, w), 0, k * 8)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        _rt.fill(_rt.at(_rt.getp(l, "List.ids"), w + 1), 0, k * 8)
    _rt.set(l, "List.len", w)
    if w == 0:
        pys_list_empty(l)


@_rt.unchecked
def pys_list_add(a: _rt.Ptr, b: _rt.Ptr) -> _rt.Ptr:
    # a + b: a new list, of atomic items where both lists' are (identities: the extends carry promoting ints')
    if (not _rt.null(_rt.getp(a, "List.ids")) and pys_rt_big_list(a) == 0) or (not _rt.null(_rt.getp(b, "List.ids")) and pys_rt_big_list(b) == 0):
        identity_pair(a, b)
    atomic = 1 if pys_rt_atomic_items(_rt.getp(a, "List.a")) != 0 and pys_rt_atomic_items(_rt.getp(b, "List.a")) != 0 else 0
    r = pys_list_make(_rt.get(a, "List.len") + _rt.get(b, "List.len"), atomic)
    pys_list_extend(r, a)
    pys_list_extend(r, b)
    return r


@_rt.unchecked
def repeat_words(a: _rt.Ptr, k: int, m: int) -> None:
    # a[0:k] repeated through a[k:m]: the copied prefix doubles, log2(m / k) copies rather than m / k
    while k < m:
        c = k if k < m - k else m - k
        _rt.cpy(_rt.at(a, k), a, c * 8)
        k += c


@_rt.unchecked
def pys_list_imul(l: _rt.Ptr, n: int) -> None:
    # xs *= n, in place
    m = _rt.get(l, "List.len")
    if n <= 0 or m == 0:
        pys_list_clear(l)
        return
    if m > _rt.sdiv(576460752303423487, n):
        raise MemoryError
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(l, _rt.word(_rt.getp(l, "List.ids"), 0))
    pys_list_reserve(l, m * n)
    repeat_words(_rt.getp(l, "List.a"), m, m * n)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        repeat_words(_rt.at(_rt.getp(l, "List.ids"), 1), m, m * n)
    _rt.set(l, "List.len", m * n)


@_rt.unchecked
def pys_list_mul(a: _rt.Ptr, n: int) -> _rt.Ptr:
    # xs * n. A new list's items are zero, so one item of zero bits (0, 0.0, False, None) is not copied
    m = _rt.get(a, "List.len")
    if m == 0:
        n = 0
    if n > 0 and m > _rt.sdiv(576460752303423487, n):
        raise MemoryError
    if not _rt.null(_rt.getp(a, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(a, _rt.word(_rt.getp(a, "List.ids"), 0))
    r = pys_list_make(m * n if n > 0 else 0, pys_rt_atomic_items(_rt.getp(a, "List.a")))
    if n > 0 and (m > 1 or _rt.word(_rt.getp(a, "List.a"), 0) != 0):
        _rt.cpy(_rt.getp(r, "List.a"), _rt.getp(a, "List.a"), m * 8)
        repeat_words(_rt.getp(r, "List.a"), m, m * n)
    if not _rt.null(_rt.getp(a, "List.ids")) and pys_rt_opt_in() != 0:
        pys_list_identity(r, _rt.word(_rt.getp(a, "List.ids"), 0))
        if n > 0:
            _rt.cpy(_rt.at(_rt.getp(r, "List.ids"), 1), _rt.at(_rt.getp(a, "List.ids"), 1), m * 8)
            repeat_words(_rt.at(_rt.getp(r, "List.ids"), 1), m, m * n)
    _rt.set(r, "List.len", m * n if n > 0 else 0)
    return r


@_rt.unchecked
def rev_words(a: _rt.Ptr, n: int) -> None:
    i = 0
    j = n - 1
    while i < j:
        x = _rt.word(a, i)
        _rt.put(a, i, _rt.word(a, j))
        _rt.put(a, j, x)
        i += 1
        j -= 1


@_rt.unchecked
def pys_list_reverse(l: _rt.Ptr) -> None:
    n = _rt.get(l, "List.len")
    rev_words(_rt.getp(l, "List.a"), n)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        rev_words(_rt.at(_rt.getp(l, "List.ids"), 1), n)


# ---- companions: pairing two lists, and the Mpzs of ints past 64 bits (runtime.c: BIGIDS)


def pys_rt_not_in_list(x: int, d: str) -> None: ...
def pys_dyn_big(lo: int, hi: _rt.Ptr) -> _rt.Ptr: ...
def pys_dyn_big_ptr(x: _rt.Ptr) -> _rt.Ptr: ...
def pys_str_eq(a: str, b: str) -> int: ...


@_rt.unchecked
def identity_pair(a: _rt.Ptr, b: _rt.Ptr) -> None:
    # before list a takes list b's items: both have their identities then, or, of promoting ints,
    # a has a companion where b has one
    if (not _rt.null(_rt.getp(a, "List.ids")) or not _rt.null(_rt.getp(b, "List.ids"))) and pys_rt_opt_in() != 0:
        kind = _rt.word(_rt.getp(a, "List.ids"), 0) if not _rt.null(_rt.getp(a, "List.ids")) else _rt.word(_rt.getp(b, "List.ids"), 0)
        if (not _rt.null(_rt.getp(a, "List.ids")) and _rt.word(_rt.getp(a, "List.ids"), 0) & 11 == 1) or (not _rt.null(_rt.getp(b, "List.ids")) and _rt.word(_rt.getp(b, "List.ids"), 0) & 11 == 1):
            kind = 1
        if kind & 3 == 3:
            if not _rt.null(_rt.getp(b, "List.ids")):
                pys_list_identity(a, kind)
            return
        pys_list_identity(a, kind)
        pys_list_identity(b, kind)


@_rt.unchecked
def pys_list_forget_identity(l: _rt.Ptr) -> None:
    # the CPython FFI twin copies every native array element back after a call: even an
    # unchanged number is a fresh Python value there
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_big_list(l) == 0:
        i = 0
        while i < _rt.get(l, "List.len"):
            box = pys_rt_list_box(_rt.word(_rt.getp(l, "List.a"), i), _rt.word(_rt.getp(l, "List.ids"), 0))
            _rt.put(_rt.getp(l, "List.ids"), i + 1, box)
            i += 1
        _rt.put(_rt.getp(l, "List.ids"), 0, _rt.word(_rt.getp(l, "List.ids"), 0) & 11)


@_rt.unchecked
def pys_rt_lbig(l: _rt.Ptr, i: int) -> _rt.Ptr:
    # the Mpz of item i where it is an int past 64 bits (its slot holds -2**63), else null: in
    # the companion of promoting ints, or in the box that an identity companion holds
    if _rt.word(_rt.getp(l, "List.a"), i) != -9223372036854775807 - 1 or _rt.null(_rt.getp(l, "List.ids")):
        return _rt.nil()
    if pys_rt_big_list(l) != 0:
        return _rt.ptr(_rt.word(_rt.getp(l, "List.ids"), i + 1))
    if _rt.word(_rt.getp(l, "List.ids"), 0) & 3 == 1 and _rt.word(_rt.getp(l, "List.ids"), i + 1) != 0 and pys_rt_opt_in() != 0:
        return pys_dyn_big_ptr(_rt.ptr(_rt.word(_rt.getp(l, "List.ids"), i + 1)))
    return _rt.nil()


@_rt.unchecked
def big_companion(l: _rt.Ptr) -> None:
    # the companion that the first int past 64 bits makes
    if _rt.null(_rt.getp(l, "List.ids")):
        if _rt.get(l, "List.cap") > 1152921504606846974:
            pys_rt_oom()
        ids = pys_alloc((_rt.get(l, "List.cap") + 1) * 8)
        _rt.put(ids, 0, 3)
        _rt.setp(l, "List.ids", ids)


@_rt.unchecked
def big_companion_item(l: _rt.Ptr, m: _rt.Ptr) -> int:
    # what the companion holds for Mpz m: the Mpz, or its box where the companion holds identities
    return _rt.addr(m) if pys_rt_big_list(l) != 0 else _rt.addr(pys_dyn_big(0, m))


@_rt.unchecked
def pys_list_set_big(l: _rt.Ptr, i: int, m: _rt.Ptr) -> None:
    n = _rt.get(l, "List.len")
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError("list assignment index out of range")
    big_companion(l)
    box = big_companion_item(l, m)
    _rt.put(_rt.getp(l, "List.ids"), i + 1, box)
    _rt.put(_rt.getp(l, "List.a"), i, -9223372036854775807 - 1)


@_rt.unchecked
def pys_list_append_big(l: _rt.Ptr, m: _rt.Ptr) -> None:
    big_companion(l)
    box = big_companion_item(l, m)
    if _rt.get(l, "List.len") == _rt.get(l, "List.cap"):
        pys_list_reserve(l, _rt.get(l, "List.len") + 1)
    n = _rt.get(l, "List.len")
    _rt.put(_rt.getp(l, "List.ids"), n + 1, box)
    _rt.set(l, "List.len", n + 1)
    _rt.put(_rt.getp(l, "List.a"), n, -9223372036854775807 - 1)


@_rt.unchecked
def pys_list_insert_big(l: _rt.Ptr, i: int, m: _rt.Ptr) -> None:
    if i < 0:
        i += _rt.get(l, "List.len")
        if i < 0:
            i = 0
    if i > _rt.get(l, "List.len"):
        i = _rt.get(l, "List.len")
    big_companion(l)
    box = big_companion_item(l, m)
    pys_list_reserve(l, _rt.get(l, "List.len") + 1)
    ids = _rt.getp(l, "List.ids")
    _rt.move(_rt.at(ids, i + 2), _rt.at(ids, i + 1), (_rt.get(l, "List.len") - i) * 8)
    _rt.put(ids, i + 1, box)
    a = _rt.getp(l, "List.a")
    _rt.move(_rt.at(a, i + 1), _rt.at(a, i), (_rt.get(l, "List.len") - i) * 8)
    _rt.put(a, i, -9223372036854775807 - 1)
    _rt.set(l, "List.len", _rt.get(l, "List.len") + 1)


@_rt.unchecked
def pys_list_big_at(l: _rt.Ptr, i: int) -> _rt.Ptr:
    # the Mpz of the item at index i (as pys_list_get takes it) whose slot holds -2**63, or null
    if i < 0:
        i += _rt.get(l, "List.len")
    return pys_rt_lbig(l, i)


# ---- searches. A list of ints or bools that has no companion (so no item past 64 bits and no
# identity boxes), and a list of strs, compare slots as runtime.c's eqitem does for the
# descriptors "i", "b" and "s", without its walk of the descriptor for each item: 1 where the
# slots' values decide, 2 where pys_str_eq does (a null slot, None, equals only None). No code of
# the program's runs in these comparisons, so the list cannot change under the search. Any other
# list compares through pys_rt_list_item_eq, which may run an __eq__: the length is read again
# for each item.


@_rt.unchecked
def scalar_items(l: _rt.Ptr, d: str) -> int:
    if _rt.byte_at(str_bytes(d), 1) != 0 or not _rt.null(_rt.getp(l, "List.ids")):
        return 0
    c = _rt.byte_at(str_bytes(d), 0)
    return 1 if c == 105 or c == 98 else 2 if c == 115 else 0


@_rt.unchecked
def str_item_eq(a: int, b: int) -> bool:
    if a != 0 and b != 0:
        return pys_str_eq(_rt.as_str(_rt.ptr(a)), _rt.as_str(_rt.ptr(b))) != 0
    return a == b


@_rt.unchecked
def index_in(l: _rt.Ptr, v: int, d: str, st: int, en: int) -> int:
    # the first i in [st, en) where l[i] == v, or -1
    if st < 0:
        st += _rt.get(l, "List.len")
        if st < 0:
            st = 0
    if en < 0:
        en += _rt.get(l, "List.len")
        if en < 0:
            en = 0
    k = scalar_items(l, d)
    if k != 0:
        e = en if en < _rt.get(l, "List.len") else _rt.get(l, "List.len")
        a = _rt.getp(l, "List.a")
        j = st
        if k == 1:
            while j < e:
                if _rt.word(a, j) == v:
                    return j
                j += 1
            return -1
        while j < e:
            if str_item_eq(_rt.word(a, j), v):
                return j
            j += 1
        return -1
    j = st
    while j < en and j < _rt.get(l, "List.len"):
        if pys_rt_list_item_eq(l, j, v, d) != 0:
            return j
        j += 1
    return -1


@_rt.unchecked
def pys_list_find(l: _rt.Ptr, v: int, d: str) -> int:
    # x in l: x's first index, or -1
    k = scalar_items(l, d)
    if k != 0:
        n = _rt.get(l, "List.len")
        a = _rt.getp(l, "List.a")
        i = 0
        if k == 1:
            while i < n:
                if _rt.word(a, i) == v:
                    return i
                i += 1
            return -1
        while i < n:
            if str_item_eq(_rt.word(a, i), v):
                return i
            i += 1
        return -1
    i = 0
    while i < _rt.get(l, "List.len"):
        if pys_rt_list_item_eq(l, i, v, d) != 0:
            return i
        i += 1
    return -1


def pys_list_index(l: _rt.Ptr, v: int, d: str, st: int, en: int) -> int:
    # list.index(v, start, stop)
    i = index_in(l, v, d, st, en)
    if i < 0:
        pys_rt_not_in_list(v, d)
    return i


def pys_list_index_as(l: _rt.Ptr, v: int, d: str, st: int, en: int, ok: int, x: int, xd: str) -> int:
    # list.index(x, start, stop) of a number x of another type than the items: v is the item
    # equal to x, if there is one (ok)
    i = index_in(l, v, d, st, en) if ok != 0 else -1
    if i < 0:
        pys_rt_not_in_list(x, xd)
    return i


@_rt.unchecked
def pys_list_count(l: _rt.Ptr, v: int, d: str) -> int:
    c = 0
    k = scalar_items(l, d)
    if k != 0:
        n = _rt.get(l, "List.len")
        a = _rt.getp(l, "List.a")
        i = 0
        if k == 1:
            while i < n:
                c += 1 if _rt.word(a, i) == v else 0
                i += 1
            return c
        while i < n:
            c += 1 if str_item_eq(_rt.word(a, i), v) else 0
            i += 1
        return c
    i = 0
    while i < _rt.get(l, "List.len"):
        c += pys_rt_list_item_eq(l, i, v, d)
        i += 1
    return c


@_rt.unchecked
def pys_list_remove(l: _rt.Ptr, v: int, d: str) -> None:
    i = pys_list_find(l, v, d)
    if i < 0:
        raise ValueError("list.remove(x): x not in list")
    if i < _rt.get(l, "List.len"):  # (an __eq__ that shrank the list past i: CPython deletes nothing)
        pys_list_del(l, i)


# ---- lists made of a range and of a bytes


@_rt.unchecked
def pys_range_list(a: int, b: int, s: int) -> _rt.Ptr:
    # list(range(a, b, s)): allocated once at its length, as CPython does. The result stays a
    # list[int] to the compiler: its array is atomic, and nothing retypes it in place
    n = pys_range_len(a, b, s)
    if n < 0:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if n > 576460752303423487:
        raise MemoryError
    l = pys_list_make(n, 1)
    items = _rt.getp(l, "List.a")
    i = 0
    while i < n:
        _rt.put(items, i, _rt.wrap_add(a, _rt.wrap_mul(i, s)))  # (wraps to the item)
        i += 1
    _rt.set(l, "List.len", n)
    return l


@_rt.unchecked
def pys_bytes_list(s: str) -> _rt.Ptr:
    # list(b): a list[int], whose array is atomic as the compiler makes them
    n = len(s)
    l = pys_list_make(n, 1)
    items = _rt.getp(l, "List.a")
    b = str_bytes(s)
    i = 0
    while i < n:
        _rt.put(items, i, _rt.byte_at(b, i))
        i += 1
    _rt.set(l, "List.len", n)
    return l


# ---------- sets: CPython's table (runtime.c's Set) ----------
# The table, its hashes and what decides a set's order are described with runtime.c's sets. keys
# and hs are arrays of mask + 1 words: hs[j] is the hash of the element in slot j, or -1 where
# the slot holds none, and keys[j] is then 0 (never used: it ends a lookup) or 1 (a dummy, which
# an insertion reuses). kb, where it is not null, holds the Mpz of each element past 64 bits.
# The hash of an int or a str is made here; runtime.c still hashes and compares the elements
# that a type descriptor describes (pys_rt_hitem, pys_rt_set_eq), whose __hash__ and __eq__ may
# run the program's code: a loop that calls them reads the table again afterwards. A probe's
# arithmetic wraps, as C's unsigned arithmetic does there, and its shift is logical.


def pys_rt_keymem(kind: int, n: int) -> _rt.Ptr: ...
def pys_rt_hitem(k: int, kind: int) -> int: ...
def pys_rt_set_eq(s: _rt.Ptr, j: int, x: int, k: int, add: int) -> int: ...
def pys_rt_set_keyerr(s: _rt.Ptr, k: int) -> None: ...
def pys_rt_bkeyerr(m: _rt.Ptr) -> None: ...
def pys_rt_khash(kind: int) -> int: ...
def pys_rt_dict_lacks(d: _rt.Ptr, k: int, h: int, m: _rt.Ptr, c: int) -> int: ...
def pys_mpz_hash(m: _rt.Ptr) -> int: ...
def pys_mpz_cmp(a: _rt.Ptr, b: _rt.Ptr) -> int: ...
def pys_rt_hash_str(s: _rt.Ptr) -> int: ...


@_rt.unchecked
def pys_rt_hash_long(v: int) -> int:
    # CPython's long_hash: |v| modulo 2**61 - 1 with v's sign, and -2 for -1
    u = _rt.wrap_sub(0, v) if v < 0 else v  # (-2**63 keeps its bits: 2**63 as an unsigned int)
    h = _rt.urem(u, 2305843009213693951)
    if v < 0:
        h = -h
    return -2 if h == -1 else h


@_rt.unchecked
def str_key_hash(k: int) -> int:
    # a str element's or key's hash, which the str keeps once made (never 0, which says it has
    # none, or -1). The hash itself is pys_hash_str's, asked for through runtime.c, where
    # tools/dictprobe.c counts the strs that are hashed
    s = _rt.ptr(k)
    h = _rt.get(s, "Str.dict_hash")
    if h == 0:
        h = pys_rt_hash_str(s)
        if h == -1:
            h = -2
        elif h == 0:
            h = 1
        _rt.set(s, "Str.dict_hash", h)
    return h


@_rt.unchecked
def set_hash(s: _rt.Ptr, k: int) -> int:
    # the hash of element k of s: kind 0 an int's, 1 a str's, else by the descriptor that kind is
    kind = _rt.get(s, "Set.kind")
    if kind == 0:
        return pys_rt_hash_long(k)
    if kind == 1:
        return str_key_hash(k)
    return pys_rt_hitem(k, kind)


@_rt.unchecked
def same_str(a: int, b: int) -> bool:
    return pys_str_eq(_rt.as_str(_rt.ptr(a)), _rt.as_str(_rt.ptr(b))) != 0


@_rt.unchecked
def probe_next(i: int, perturb: int, mask: int) -> int:
    # the slot after i's run: CPython's step, by the hash bits left in perturb
    return _rt.wrap_add(_rt.wrap_add(_rt.wrap_mul(i, 5), 1), perturb) & mask


@_rt.unchecked
def pys_rt_sbig(s: _rt.Ptr, j: int) -> _rt.Ptr:
    # the Mpz of the element in slot j where it is an int past 64 bits (its slot holds a
    # sentinel: -2**63, or -2**63 + 1), else null
    if _rt.word(_rt.getp(s, "Set.keys"), j) <= -9223372036854775807 and not _rt.null(_rt.getp(s, "Set.kb")) and pys_rt_opt_in() != 0:
        return _rt.ptr(_rt.word(_rt.getp(s, "Set.kb"), j))
    return _rt.nil()


@_rt.unchecked
def pys_rt_set_table(s: _rt.Ptr, size: int) -> None:
    # an empty table of size slots. The 8 slots of a new or cleared set are scanned whatever its
    # kind: the compiler gives an empty set from a template the kind of the type its caller
    # expects only after it is made. A larger table comes from insertions, of the set's own kind
    if size > 8:
        _rt.setp(s, "Set.keys", pys_rt_keymem(_rt.get(s, "Set.kind"), size))
    else:
        _rt.setp(s, "Set.keys", pys_alloc(size * 8))
    hs = pys_alloc_atomic(size * 8)
    _rt.fill(hs, 255, size * 8)
    _rt.setp(s, "Set.hs", hs)
    _rt.set(s, "Set.mask", size - 1)
    _rt.set(s, "Set.fill", 0)
    _rt.setp(s, "Set.kb", _rt.nil())


@_rt.unchecked
def pys_set_new(kind: int) -> _rt.Ptr:
    # (the allocator adds its byte of slack: the header keeps 64 bytes)
    s = pys_alloc(_rt.sizeof("Set") - 1)
    _rt.set(s, "Set.kind", kind)
    pys_rt_set_table(s, 8)
    return s


@_rt.unchecked
def set_look(s: _rt.Ptr, k: int, h: int) -> int:
    # set_lookkey: k's slot, else the empty one that ends its probes. A probe looks at up to
    # ten adjacent slots (one at the end of the table), then moves on. An __eq__ that changed
    # the table or the slot it compared makes the lookup start again
    while True:
        mask = _rt.get(s, "Set.mask")
        i = h & mask
        perturb = h
        again = False
        while not again:
            probes = 9 if i + 9 <= mask else 0
            j = i
            while True:
                hj = _rt.word(_rt.getp(s, "Set.hs"), j)
                if hj == h:
                    x = _rt.word(_rt.getp(s, "Set.keys"), j)
                    if x == k:
                        return j
                    kind = _rt.get(s, "Set.kind")
                    if kind == 1:
                        if same_str(x, k):
                            return j
                    elif kind > 1:
                        eq = pys_rt_set_eq(s, j, x, k, 0)
                        if eq < 0:
                            again = True
                            break
                        if eq != 0:
                            return j
                elif hj == -1 and _rt.word(_rt.getp(s, "Set.keys"), j) == 0:
                    return j
                if probes == 0:
                    break
                probes -= 1
                j += 1
            perturb = _rt.lshr(perturb, 5)
            i = probe_next(i, perturb, mask)
    return -1  # (not reached: only a return leaves the loop)


@_rt.unchecked
def pys_rt_set_clean(s: _rt.Ptr, k: int, h: int) -> int:
    # set_insert_clean: k into a table that has no dummy, nor k; its slot
    mask = _rt.get(s, "Set.mask")
    hs = _rt.getp(s, "Set.hs")
    i = h & mask
    perturb = h
    e = i
    while True:
        e = i
        if _rt.word(hs, e) == -1:
            break
        if i + 9 <= mask:
            j = 0
            while j < 9:
                e += 1
                if _rt.word(hs, e) == -1:
                    break
                j += 1
            if j < 9:
                break
        perturb = _rt.lshr(perturb, 5)
        i = probe_next(i, perturb, mask)
    _rt.put(_rt.getp(s, "Set.keys"), e, k)
    _rt.put(hs, e, h)
    return e


@_rt.unchecked
def big_sentinel(h: int) -> int:
    # what the slot of an element past 64 bits of hash h holds: -2**63, or -2**63 + 1 where h
    # is -2**63's own hash (-4), so that no 64-bit element of its hash is its sentinel
    return -9223372036854775807 if h == -4 else -9223372036854775807 - 1


@_rt.unchecked
def set_big_find(s: _rt.Ptr, m: _rt.Ptr, h: int) -> int:
    # the slot of element m, an int past 64 bits of hash h; else -1 less the slot that takes it:
    # the last dummy its probes passed, or the empty slot that ends them (which holds no key)
    k = big_sentinel(h)
    mask = _rt.get(s, "Set.mask")
    hs = _rt.getp(s, "Set.hs")
    keys = _rt.getp(s, "Set.keys")
    i = h & mask
    perturb = h
    free = -1
    while True:
        probes = 9 if i + 9 <= mask else 0
        j = i
        while True:
            hj = _rt.word(hs, j)
            if hj == h and _rt.word(keys, j) == k:
                x = pys_rt_sbig(s, j)
                if not _rt.null(x) and (x is m or pys_mpz_cmp(x, m) == 0):
                    return j
            elif hj == -1:
                if _rt.word(keys, j) == 0:
                    return -1 - (free if free >= 0 else j)
                free = j
            if probes == 0:
                break
            probes -= 1
            j += 1
        perturb = _rt.lshr(perturb, 5)
        i = probe_next(i, perturb, mask)
    return -1  # (not reached)


@_rt.cold
@_rt.unchecked
def set_big_put(s: _rt.Ptr, j: int, m: _rt.Ptr) -> None:
    # slot j's element is past 64 bits: its Mpz m, in kb, which the first one makes
    if _rt.null(_rt.getp(s, "Set.kb")):
        _rt.setp(s, "Set.kb", pys_alloc((_rt.get(s, "Set.mask") + 1) * 8))
    _rt.put(_rt.getp(s, "Set.kb"), j, _rt.addr(m))


@_rt.unchecked
def set_resize(s: _rt.Ptr, minused: int) -> None:
    # set_table_resize: the first size above minused, without dummies
    size = 8
    m = _rt.get(s, "Set.mask")
    keys = _rt.getp(s, "Set.keys")
    hs = _rt.getp(s, "Set.hs")
    kb = _rt.getp(s, "Set.kb")
    while size <= minused:
        size = size << 1
    if size == 8 and m == 7 and _rt.get(s, "Set.fill") == _rt.get(s, "Set.len"):
        return  # (the small table without dummies stays as it is)
    pys_rt_set_table(s, size)
    _rt.set(s, "Set.fill", _rt.get(s, "Set.len"))
    i = 0
    if _rt.null(kb):
        while i <= m:
            h = _rt.word(hs, i)
            if h != -1:
                pys_rt_set_clean(s, _rt.word(keys, i), h)
            i += 1
        return
    while i <= m:
        h = _rt.word(hs, i)
        if h != -1:
            k = _rt.word(keys, i)
            e = pys_rt_set_clean(s, k, h)
            if k <= -9223372036854775807 and _rt.word(kb, i) != 0:
                set_big_put(s, e, _rt.ptr(_rt.word(kb, i)))
        i += 1


@_rt.unchecked
def set_grown(s: _rt.Ptr) -> int:
    # the elements a rebuilt table is sized for: 4 times those it has (2 times above 50000)
    n = _rt.get(s, "Set.len")
    return n * 2 if n > 50000 else n * 4


@_rt.unchecked
def set_add(s: _rt.Ptr, k: int, h: int) -> None:
    # set_add_entry: k, whose hash is h, unless an equal element is there; into the last dummy
    # its probes passed, else the empty slot that ends them. An __eq__ that changed the table or
    # the slot it compared makes it start again, and so does one that filled that dummy (or
    # dropped it, in a rebuild of the small table): k would overwrite another element
    while True:
        mask = _rt.get(s, "Set.mask")
        i = h & mask
        perturb = h
        free = -1
        again = False
        while not again:
            probes = 9 if i + 9 <= mask else 0
            j = i
            while True:
                hj = _rt.word(_rt.getp(s, "Set.hs"), j)
                if hj == h:
                    x = _rt.word(_rt.getp(s, "Set.keys"), j)
                    if x == k:
                        return
                    kind = _rt.get(s, "Set.kind")
                    if kind == 1:
                        if same_str(x, k):
                            return
                    elif kind > 1:
                        eq = pys_rt_set_eq(s, j, x, k, 1)
                        if eq < 0:
                            again = True
                            break
                        if eq != 0:
                            return
                elif hj == -1:
                    keys = _rt.getp(s, "Set.keys")
                    if _rt.word(keys, j) != 0:
                        free = j
                    else:
                        hs = _rt.getp(s, "Set.hs")
                        if free >= 0:
                            if _rt.get(s, "Set.kind") > 1 and not (_rt.word(hs, free) == -1 and _rt.word(keys, free) != 0):
                                again = True
                                break
                            _rt.put(keys, free, k)
                            _rt.put(hs, free, h)
                            _rt.set(s, "Set.len", _rt.get(s, "Set.len") + 1)
                            return
                        _rt.put(keys, j, k)
                        _rt.put(hs, j, h)
                        _rt.set(s, "Set.len", _rt.get(s, "Set.len") + 1)
                        fill = _rt.get(s, "Set.fill") + 1
                        _rt.set(s, "Set.fill", fill)
                        if fill * 5 >= mask * 3:
                            set_resize(s, set_grown(s))
                        return
                if probes == 0:
                    break
                probes -= 1
                j += 1
            perturb = _rt.lshr(perturb, 5)
            i = probe_next(i, perturb, mask)


@_rt.unchecked
def set_discard(s: _rt.Ptr, k: int, h: int) -> bool:
    # set_discard_entry: was k there (s's table as it is once the lookup is done: an __eq__ may
    # replace it)
    j = set_look(s, k, h)
    hs = _rt.getp(s, "Set.hs")
    if _rt.word(hs, j) == -1:
        return False
    _rt.put(_rt.getp(s, "Set.keys"), j, 1)
    _rt.put(hs, j, -1)
    _rt.set(s, "Set.len", _rt.get(s, "Set.len") - 1)
    return True


@_rt.unchecked
def set_has(s: _rt.Ptr, k: int, h: int) -> bool:
    j = set_look(s, k, h)
    return _rt.word(_rt.getp(s, "Set.hs"), j) != -1


@_rt.unchecked
def set_big_add(s: _rt.Ptr, m: _rt.Ptr, h: int) -> None:
    # set_add, set_discard and set_has of m, an int past 64 bits of hash h
    j = set_big_find(s, m, h)
    if j >= 0:
        return
    j = -1 - j
    keys = _rt.getp(s, "Set.keys")
    dummy = _rt.word(keys, j) != 0
    _rt.put(keys, j, big_sentinel(h))
    _rt.put(_rt.getp(s, "Set.hs"), j, h)
    set_big_put(s, j, m)
    _rt.set(s, "Set.len", _rt.get(s, "Set.len") + 1)
    if not dummy:
        fill = _rt.get(s, "Set.fill") + 1
        _rt.set(s, "Set.fill", fill)
        if fill * 5 >= _rt.get(s, "Set.mask") * 3:
            set_resize(s, set_grown(s))


@_rt.unchecked
def set_big_discard(s: _rt.Ptr, m: _rt.Ptr, h: int) -> bool:
    j = set_big_find(s, m, h)
    if j < 0:
        return False
    _rt.put(_rt.getp(s, "Set.keys"), j, 1)
    _rt.put(_rt.getp(s, "Set.hs"), j, -1)
    _rt.put(_rt.getp(s, "Set.kb"), j, 0)
    _rt.set(s, "Set.len", _rt.get(s, "Set.len") - 1)
    return True


@_rt.unchecked
def set_add_any(s: _rt.Ptr, k: int, h: int, m: _rt.Ptr) -> None:
    # the same of element k of hash h, past 64 bits where its Mpz m is not null: for an element
    # taken from a table (pys_rt_sbig) or a list (pys_rt_lbig)
    if _rt.null(m):
        set_add(s, k, h)
    else:
        set_big_add(s, m, h)


@_rt.unchecked
def set_discard_any(s: _rt.Ptr, k: int, h: int, m: _rt.Ptr) -> bool:
    return set_discard(s, k, h) if _rt.null(m) else set_big_discard(s, m, h)


@_rt.unchecked
def set_has_any(s: _rt.Ptr, k: int, h: int, m: _rt.Ptr) -> bool:
    return set_has(s, k, h) if _rt.null(m) else set_big_find(s, m, h) >= 0


@_rt.unchecked
def set_merge(s: _rt.Ptr, o: _rt.Ptr) -> None:
    # set_merge: o's elements into s
    n = _rt.get(o, "Set.len")
    if o is s or n == 0:
        return
    if (_rt.get(s, "Set.fill") + n) * 5 >= _rt.get(s, "Set.mask") * 3:
        set_resize(s, (_rt.get(s, "Set.len") + n) * 2)
    size = _rt.get(o, "Set.mask") + 1
    if _rt.get(s, "Set.fill") == 0 and _rt.get(s, "Set.mask") == size - 1 and _rt.get(o, "Set.fill") == n:
        # tables of one size, o's without dummies: a copy
        _rt.cpy(_rt.getp(s, "Set.keys"), _rt.getp(o, "Set.keys"), size * 8)
        _rt.cpy(_rt.getp(s, "Set.hs"), _rt.getp(o, "Set.hs"), size * 8)
        if not _rt.null(_rt.getp(o, "Set.kb")):  # (s, with no fill, has no kb)
            kb = pys_alloc(size * 8)
            _rt.cpy(kb, _rt.getp(o, "Set.kb"), size * 8)
            _rt.setp(s, "Set.kb", kb)
        _rt.set(s, "Set.fill", n)
        _rt.set(s, "Set.len", n)
        return
    i = 0
    if _rt.get(s, "Set.fill") == 0:
        _rt.set(s, "Set.fill", n)
        _rt.set(s, "Set.len", n)
        while i < size:
            h = _rt.word(_rt.getp(o, "Set.hs"), i)
            if h != -1:
                e = pys_rt_set_clean(s, _rt.word(_rt.getp(o, "Set.keys"), i), h)
                m = pys_rt_sbig(o, i)
                if not _rt.null(m):
                    set_big_put(s, e, m)
            i += 1
        return
    while i <= _rt.get(o, "Set.mask"):  # (an __eq__ may change o: its table is read again)
        h = _rt.word(_rt.getp(o, "Set.hs"), i)
        if h != -1:
            set_add_any(s, _rt.word(_rt.getp(o, "Set.keys"), i), h, pys_rt_sbig(o, i))
        i += 1


@_rt.unchecked
def set_shrink(s: _rt.Ptr) -> None:
    # after a difference: a rebuild once a quarter of the slots are dummies
    if _rt.get(s, "Set.fill") - _rt.get(s, "Set.len") > _rt.lshr(_rt.get(s, "Set.mask"), 2):
        set_resize(s, set_grown(s))


@_rt.unchecked
def set_sym_update(s: _rt.Ptr, o: _rt.Ptr) -> None:
    # set_symmetric_difference_update_set. (An element's __eq__ may change the sets these loops
    # go through: each takes an element and its hash before it looks them up)
    i = 0
    while i <= _rt.get(o, "Set.mask"):
        k = _rt.word(_rt.getp(o, "Set.keys"), i)
        h = _rt.word(_rt.getp(o, "Set.hs"), i)
        if h != -1:
            m = pys_rt_sbig(o, i)
            if not set_discard_any(s, k, h, m):
                set_add_any(s, k, h, m)
        i += 1


@_rt.unchecked
def set_subset(a: _rt.Ptr, b: _rt.Ptr) -> bool:
    # set_issubset of a set
    if _rt.get(a, "Set.len") > _rt.get(b, "Set.len"):
        return False
    i = 0
    while i <= _rt.get(a, "Set.mask"):
        h = _rt.word(_rt.getp(a, "Set.hs"), i)
        if h != -1 and not set_has_any(b, _rt.word(_rt.getp(a, "Set.keys"), i), h, pys_rt_sbig(a, i)):
            return False
        i += 1
    return True


# The entry points that hash an element stay calls in a program's AOT build (@_rt.noinline), as
# runtime.c's dict lookups do: copied into every use, they made executables larger for no speed.


@_rt.noinline
@_rt.unchecked
def pys_set_add(s: _rt.Ptr, k: int) -> None:
    set_add(s, k, set_hash(s, k))


@_rt.noinline
@_rt.unchecked
def pys_set_has(s: _rt.Ptr, k: int) -> int:
    return 1 if set_has(s, k, set_hash(s, k)) else 0


@_rt.noinline
@_rt.unchecked
def pys_set_discard(s: _rt.Ptr, k: int) -> None:
    set_discard(s, k, set_hash(s, k))


@_rt.noinline
@_rt.unchecked
def pys_set_remove(s: _rt.Ptr, k: int) -> None:
    if not set_discard(s, k, set_hash(s, k)):
        pys_rt_set_keyerr(s, k)


@_rt.unchecked
def pys_rt_set_pop_slot(s: _rt.Ptr) -> int:
    # set_pop's slot: that of the first element from the finger on
    if _rt.get(s, "Set.len") == 0:
        _rt.fail("KeyError", "'pop from an empty set'")
    mask = _rt.get(s, "Set.mask")
    hs = _rt.getp(s, "Set.hs")
    i = _rt.get(s, "Set.finger") & mask
    while _rt.word(hs, i) == -1:
        i += 1
        if i > mask:
            i = 0
    return i


@_rt.unchecked
def pys_set_slot_del(s: _rt.Ptr, j: int) -> None:
    # the element in slot j leaves a dummy
    _rt.put(_rt.getp(s, "Set.keys"), j, 1)
    _rt.put(_rt.getp(s, "Set.hs"), j, -1)
    if not _rt.null(_rt.getp(s, "Set.kb")):
        _rt.put(_rt.getp(s, "Set.kb"), j, 0)
    _rt.set(s, "Set.len", _rt.get(s, "Set.len") - 1)


@_rt.unchecked
def pys_rt_set_take(s: _rt.Ptr, i: int) -> None:
    # and the finger moves past it (set_pop)
    pys_set_slot_del(s, i)
    _rt.set(s, "Set.finger", i + 1)


@_rt.unchecked
def pys_set_big_pop(s: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    # s.pop() of a set of ints, as a promoting int: its two words, by value
    i = pys_rt_set_pop_slot(s)
    m = pys_rt_sbig(s, i)
    k = _rt.word(_rt.getp(s, "Set.keys"), i)
    pys_rt_set_take(s, i)
    return (k if _rt.null(m) else 0), m


@_rt.unchecked
def pys_set_pop(s: _rt.Ptr) -> int:
    i = pys_rt_set_pop_slot(s)
    if not _rt.null(pys_rt_sbig(s, i)):
        raise OverflowError("Python int too large to convert to C long")  # (pys_set_big_pop's)
    k = _rt.word(_rt.getp(s, "Set.keys"), i)
    pys_rt_set_take(s, i)
    return k


# s.add(x), x in s, s.discard(x) and s.remove(x) of a set of ints and a promoting int x, {lo, m}:
# one that fits as its 64-bit int; past 64 bits, its Mpz m, of CPython's hash


@_rt.noinline
@_rt.unchecked
def pys_set_big_add(s: _rt.Ptr, lo: int, m: _rt.Ptr) -> None:
    if _rt.null(m):
        pys_set_add(s, lo)
    else:
        set_big_add(s, m, pys_mpz_hash(m))


@_rt.noinline
@_rt.unchecked
def pys_set_big_has(s: _rt.Ptr, lo: int, m: _rt.Ptr) -> int:
    if _rt.null(m):
        return pys_set_has(s, lo)
    return 1 if set_big_find(s, m, pys_mpz_hash(m)) >= 0 else 0


@_rt.noinline
@_rt.unchecked
def pys_set_big_discard(s: _rt.Ptr, lo: int, m: _rt.Ptr) -> None:
    if _rt.null(m):
        pys_set_discard(s, lo)
    else:
        set_big_discard(s, m, pys_mpz_hash(m))


@_rt.noinline
@_rt.unchecked
def pys_set_big_remove(s: _rt.Ptr, lo: int, m: _rt.Ptr) -> None:
    if _rt.null(m):
        pys_set_remove(s, lo)
    elif not set_big_discard(s, m, pys_mpz_hash(m)):
        pys_rt_bkeyerr(m)


def pys_set_big_key(s: _rt.Ptr, i: int) -> _rt.Ptr:
    # the Mpz of the element in slot i, where pys_set_key gave -2**63 or -2**63 + 1
    return pys_rt_sbig(s, i)


@_rt.unchecked
def pys_set_clear(s: _rt.Ptr) -> None:
    pys_rt_set_table(s, 8)
    _rt.set(s, "Set.len", 0)


@_rt.unchecked
def pys_set_copy(s: _rt.Ptr) -> _rt.Ptr:
    # set(o), s.copy() and frozenset(o) of a set o: o merged into a new set
    r = pys_set_new(_rt.get(s, "Set.kind"))
    set_merge(r, s)
    return r


def pys_set_update(s: _rt.Ptr, o: _rt.Ptr) -> None:
    # s.update(o) (s |= o) of a set o; of a list (any other iterable's items), one insertion per
    # item; of a dict, one resize for all its keys, then theirs in order
    set_merge(s, o)


@_rt.unchecked
def list_elem_hash(s: _rt.Ptr, k: int, m: _rt.Ptr) -> int:
    # the hash of a list's item k as an element of s (m: its Mpz past 64 bits), taken before a
    # lookup: an __eq__ may change the list
    return set_hash(s, k) if _rt.null(m) else pys_mpz_hash(m)


@_rt.unchecked
def pys_set_update_list(s: _rt.Ptr, l: _rt.Ptr) -> None:
    i = 0
    while i < _rt.get(l, "List.len"):
        k = _rt.word(_rt.getp(l, "List.a"), i)
        m = pys_rt_lbig(l, i)
        set_add_any(s, k, list_elem_hash(s, k, m), m)
        i += 1


@_rt.unchecked
def dict_live(d: _rt.Ptr, e: int) -> bool:
    # is entry e of dict d live: a table hashed by CPython's hash (2 on its kind) keeps -1 for a
    # hole's hash, another 0 for its hash and its key
    h = _rt.word(_rt.getp(d, "Dict.hs"), e)
    if _rt.get(d, "Dict.kind") & 2 != 0:
        return h != -1
    return h != 0 or _rt.word(_rt.getp(d, "Dict.keys"), e) != 0


@_rt.unchecked
def dict_key_big(d: _rt.Ptr, e: int) -> _rt.Ptr:
    # the Mpz of entry e's key where it is an int past 64 bits (its slot holds -2**63), else null
    if _rt.word(_rt.getp(d, "Dict.keys"), e) == -9223372036854775807 - 1 and not _rt.null(_rt.getp(d, "Dict.kb")) and pys_rt_opt_in() != 0:
        return _rt.ptr(_rt.word(_rt.getp(d, "Dict.kb"), e))
    return _rt.nil()


@_rt.unchecked
def dict_key_hash(s: _rt.Ptr, d: _rt.Ptr, e: int, c: int) -> int:
    # the set's hash of d's key e: CPython's takes the dict's, which a table hashed by CPython's
    # hash keeps (c)
    if c != 0:
        return _rt.word(_rt.getp(d, "Dict.hs"), e)
    return set_hash(s, _rt.word(_rt.getp(d, "Dict.keys"), e))


@_rt.cold
@_rt.unchecked
def set_dict_big(s: _rt.Ptr, d: _rt.Ptr, c: int, op: int) -> None:
    # s.update(d) (op 0), the removal of d's keys from s (1) and s ^= d (2) of a dict of int keys
    # that may hold a key past 64 bits, whose hash is CPython's of it: a path of its own, so that
    # the loops of the others stay as they were
    e = 0
    while e < _rt.get(d, "Dict.n"):
        if dict_live(d, e):
            m = dict_key_big(d, e)
            k = _rt.word(_rt.getp(d, "Dict.keys"), e)
            h = dict_key_hash(s, d, e, c) if _rt.null(m) else pys_mpz_hash(m)
            if op == 0 or not set_discard_any(s, k, h, m):
                if op != 1:
                    set_add_any(s, k, h, m)
        e += 1


@_rt.unchecked
def dict_has_big_keys(d: _rt.Ptr) -> bool:
    return not _rt.null(_rt.getp(d, "Dict.kb")) and pys_rt_opt_in() != 0


@_rt.unchecked
def pys_set_update_dict(s: _rt.Ptr, d: _rt.Ptr) -> None:
    c = pys_rt_khash(_rt.get(d, "Dict.kind"))
    if (_rt.get(s, "Set.fill") + _rt.get(d, "Dict.len")) * 5 >= _rt.get(s, "Set.mask") * 3:
        set_resize(s, (_rt.get(s, "Set.len") + _rt.get(d, "Dict.len")) * 2)
    if dict_has_big_keys(d):
        set_dict_big(s, d, c, 0)
        return
    e = 0
    while e < _rt.get(d, "Dict.n"):
        if dict_live(d, e):
            set_add(s, _rt.word(_rt.getp(d, "Dict.keys"), e), dict_key_hash(s, d, e, c))
        e += 1


def pys_set_union_more(r: _rt.Ptr, s: _rt.Ptr, o: _rt.Ptr) -> None:
    # s.union(..., o, ...) after the first: o, unless it is s itself (r: the union so far)
    if o is not s:
        set_merge(r, o)


def pys_set_or(a: _rt.Ptr, b: _rt.Ptr) -> _rt.Ptr:
    r = pys_set_copy(a)
    if b is not a:
        set_merge(r, b)
    return r


@_rt.unchecked
def pys_set_and(a: _rt.Ptr, b: _rt.Ptr) -> _rt.Ptr:
    # s & o (set_intersection): the elements of the smaller set (o if both have as many), in its
    # order, that the other has
    if a is b:
        return pys_set_copy(a)
    r = pys_set_new(_rt.get(a, "Set.kind"))
    if _rt.get(b, "Set.len") > _rt.get(a, "Set.len"):
        t = a
        a = b
        b = t
    i = 0
    while i <= _rt.get(b, "Set.mask"):
        k = _rt.word(_rt.getp(b, "Set.keys"), i)
        h = _rt.word(_rt.getp(b, "Set.hs"), i)
        if h != -1:
            m = pys_rt_sbig(b, i)
            if set_has_any(a, k, h, m):
                set_add_any(r, k, h, m)
        i += 1
    return r


@_rt.unchecked
def pys_set_and_list(s: _rt.Ptr, l: _rt.Ptr) -> _rt.Ptr:
    # of a list, its items in order that s has, until there are as many as s has
    r = pys_set_new(_rt.get(s, "Set.kind"))
    i = 0
    while i < _rt.get(l, "List.len"):
        k = _rt.word(_rt.getp(l, "List.a"), i)
        m = pys_rt_lbig(l, i)
        h = list_elem_hash(s, k, m)
        if set_has_any(s, k, h, m):
            set_add_any(r, k, h, m)
            if _rt.get(r, "Set.len") >= _rt.get(s, "Set.len"):
                break
        i += 1
    return r


def pys_set_assign(s: _rt.Ptr, t: _rt.Ptr) -> None:
    # s &= o and s.intersection_update(...): s takes the table of the intersection
    _rt.set(s, "Set.len", _rt.get(t, "Set.len"))
    _rt.set(s, "Set.fill", _rt.get(t, "Set.fill"))
    _rt.set(s, "Set.mask", _rt.get(t, "Set.mask"))
    _rt.setp(s, "Set.keys", _rt.getp(t, "Set.keys"))
    _rt.setp(s, "Set.hs", _rt.getp(t, "Set.hs"))
    _rt.setp(s, "Set.kb", _rt.getp(t, "Set.kb"))


@_rt.unchecked
def pys_set_isub(s: _rt.Ptr, o: _rt.Ptr) -> None:
    # s -= o and s.difference_update(o) (set_difference_update_internal): o's elements discarded
    # (those of s & o, if o is more than 8 times larger)
    if s is o:
        pys_set_clear(s)
        return
    if _rt.get(o, "Set.len") >> 3 > _rt.get(s, "Set.len"):
        o = pys_set_and(s, o)
    i = 0
    while i <= _rt.get(o, "Set.mask"):
        h = _rt.word(_rt.getp(o, "Set.hs"), i)
        if h != -1:
            set_discard_any(s, _rt.word(_rt.getp(o, "Set.keys"), i), h, pys_rt_sbig(o, i))
        i += 1
    set_shrink(s)


@_rt.unchecked
def pys_set_isub_list(s: _rt.Ptr, l: _rt.Ptr) -> None:
    i = 0
    while i < _rt.get(l, "List.len"):
        k = _rt.word(_rt.getp(l, "List.a"), i)
        m = pys_rt_lbig(l, i)
        set_discard_any(s, k, list_elem_hash(s, k, m), m)
        i += 1
    set_shrink(s)


@_rt.unchecked
def pys_set_sub(a: _rt.Ptr, b: _rt.Ptr) -> _rt.Ptr:
    # s - o (set_difference): a copy of s less o's elements if s has more than 4 times as many,
    # else the elements of s that o has not, inserted into a new set
    if _rt.get(a, "Set.len") >> 2 > _rt.get(b, "Set.len"):
        r = pys_set_copy(a)
        pys_set_isub(r, b)
        return r
    r = pys_set_new(_rt.get(a, "Set.kind"))
    i = 0
    while i <= _rt.get(a, "Set.mask"):
        k = _rt.word(_rt.getp(a, "Set.keys"), i)
        h = _rt.word(_rt.getp(a, "Set.hs"), i)
        if h != -1:
            m = pys_rt_sbig(a, i)
            if not set_has_any(b, k, h, m):
                set_add_any(r, k, h, m)
        i += 1
    return r


def pys_set_sub_list(s: _rt.Ptr, l: _rt.Ptr) -> _rt.Ptr:
    r = pys_set_copy(s)
    pys_set_isub_list(r, l)
    return r


@_rt.unchecked
def pys_set_sub_dict(s: _rt.Ptr, d: _rt.Ptr) -> _rt.Ptr:
    # of a dict, as of a set, with its keys
    c = pys_rt_khash(_rt.get(d, "Dict.kind"))
    if _rt.get(s, "Set.len") >> 2 > _rt.get(d, "Dict.len"):
        r = pys_set_copy(s)
        if dict_has_big_keys(d):
            set_dict_big(r, d, c, 1)
        else:
            e = 0
            while e < _rt.get(d, "Dict.n"):
                if dict_live(d, e):
                    set_discard(r, _rt.word(_rt.getp(d, "Dict.keys"), e), dict_key_hash(r, d, e, c))
                e += 1
        set_shrink(r)
        return r
    r = pys_set_new(_rt.get(s, "Set.kind"))
    i = 0
    while i <= _rt.get(s, "Set.mask"):
        k = _rt.word(_rt.getp(s, "Set.keys"), i)
        h = _rt.word(_rt.getp(s, "Set.hs"), i)
        if h != -1:
            m = pys_rt_sbig(s, i)
            if pys_rt_dict_lacks(d, k, h, m, c) != 0:
                set_add_any(r, k, h, m)
        i += 1
    return r


def pys_set_xor(a: _rt.Ptr, b: _rt.Ptr) -> _rt.Ptr:
    # s ^ o (set_symmetric_difference): a new set of o's elements (a list's items, a dict's
    # keys), with each element of s then removed if it is there, else added
    r = pys_set_new(_rt.get(a, "Set.kind"))
    set_merge(r, b)
    set_sym_update(r, a)
    return r


def pys_set_xor_list(s: _rt.Ptr, l: _rt.Ptr) -> _rt.Ptr:
    r = pys_set_new(_rt.get(s, "Set.kind"))
    pys_set_update_list(r, l)
    set_sym_update(r, s)
    return r


def pys_set_xor_dict(s: _rt.Ptr, d: _rt.Ptr) -> _rt.Ptr:
    r = pys_set_new(_rt.get(s, "Set.kind"))
    pys_set_update_dict(r, d)
    set_sym_update(r, s)
    return r


def pys_set_ixor(s: _rt.Ptr, o: _rt.Ptr) -> None:
    # s ^= o and s.symmetric_difference_update(o): each element of o removed from s if it is
    # there, else added (s ^= s empties s); a list's items go through a set of them first, a
    # dict's keys do not
    if s is o:
        pys_set_clear(s)
    else:
        set_sym_update(s, o)


def pys_set_ixor_list(s: _rt.Ptr, l: _rt.Ptr) -> None:
    o = pys_set_new(_rt.get(s, "Set.kind"))
    pys_set_update_list(o, l)
    set_sym_update(s, o)


@_rt.unchecked
def pys_set_ixor_dict(s: _rt.Ptr, d: _rt.Ptr) -> None:
    c = pys_rt_khash(_rt.get(d, "Dict.kind"))
    if dict_has_big_keys(d):
        set_dict_big(s, d, c, 2)
        return
    e = 0
    while e < _rt.get(d, "Dict.n"):
        if dict_live(d, e):
            k = _rt.word(_rt.getp(d, "Dict.keys"), e)
            h = dict_key_hash(s, d, e, c)
            if not set_discard(s, k, h):
                set_add(s, k, h)
        e += 1


def pys_set_cmp(a: _rt.Ptr, b: _rt.Ptr, op: int) -> int:
    # a op b for op 0..5 = < <= > >= == != (set_richcompare): subsets and equality
    n = _rt.get(a, "Set.len")
    m = _rt.get(b, "Set.len")
    if op == 0:
        return 1 if n < m and set_subset(a, b) else 0
    if op == 1:
        return 1 if set_subset(a, b) else 0
    if op == 2:
        return 1 if n > m and set_subset(b, a) else 0
    if op == 3:
        return 1 if set_subset(b, a) else 0
    if op == 4:
        return 1 if n == m and set_subset(a, b) else 0
    return 1 if n != m or not set_subset(a, b) else 0


def pys_set_le_list(s: _rt.Ptr, l: _rt.Ptr) -> int:
    # s.issubset(l), s.issuperset(l) and s.isdisjoint(...)
    return 1 if _rt.get(pys_set_and_list(s, l), "Set.len") == _rt.get(s, "Set.len") else 0


@_rt.unchecked
def pys_set_ge_list(s: _rt.Ptr, l: _rt.Ptr) -> int:
    i = 0
    while i < _rt.get(l, "List.len"):
        k = _rt.word(_rt.getp(l, "List.a"), i)
        m = pys_rt_lbig(l, i)
        if not set_has_any(s, k, list_elem_hash(s, k, m), m):
            return 0
        i += 1
    return 1


@_rt.unchecked
def pys_set_isdisjoint(a: _rt.Ptr, b: _rt.Ptr) -> int:
    if a is b:
        return 1 if _rt.get(a, "Set.len") == 0 else 0
    if _rt.get(b, "Set.len") > _rt.get(a, "Set.len"):
        t = a
        a = b
        b = t
    i = 0
    while i <= _rt.get(b, "Set.mask"):
        h = _rt.word(_rt.getp(b, "Set.hs"), i)
        if h != -1 and set_has_any(a, _rt.word(_rt.getp(b, "Set.keys"), i), h, pys_rt_sbig(b, i)):
            return 0
        i += 1
    return 1


@_rt.unchecked
def pys_set_isdisjoint_list(s: _rt.Ptr, l: _rt.Ptr) -> int:
    i = 0
    while i < _rt.get(l, "List.len"):
        k = _rt.word(_rt.getp(l, "List.a"), i)
        m = pys_rt_lbig(l, i)
        if set_has_any(s, k, list_elem_hash(s, k, m), m):
            return 0
        i += 1
    return 1


@_rt.unchecked
def pys_set_next(s: _rt.Ptr, i: int, used: int) -> int:
    # for loops: the slot of the next element from slot i, or -1 at the end, failing like
    # CPython's set iterator when the set changed size meanwhile (used: its len when the loop
    # started)
    if _rt.get(s, "Set.len") != used:
        raise RuntimeError("Set changed size during iteration")
    mask = _rt.get(s, "Set.mask")
    hs = _rt.getp(s, "Set.hs")
    while i <= mask and _rt.word(hs, i) == -1:
        i += 1
    return -1 if i > mask else i


def pys_set_key(s: _rt.Ptr, i: int) -> int:
    return _rt.word(_rt.getp(s, "Set.keys"), i)


@_rt.unchecked
def pys_set_list(s: _rt.Ptr) -> _rt.Ptr:
    # list(s), sorted(s), ...: the elements in the order a loop sees them (an int set's table
    # past 8 slots is atomic; an int past 64 bits: -2**63 and the list's companion of them)
    keys = _rt.getp(s, "Set.keys")
    hs = _rt.getp(s, "Set.hs")
    mask = _rt.get(s, "Set.mask")
    l = pys_list_make(_rt.get(s, "Set.len"), pys_rt_atomic_items(keys))
    items = _rt.getp(l, "List.a")
    n = 0
    i = 0
    while i <= mask:
        if _rt.word(hs, i) != -1:
            m = pys_rt_sbig(s, i)
            if _rt.null(m):
                _rt.put(items, n, _rt.word(keys, i))
            else:
                big_companion(l)
                _rt.put(_rt.getp(l, "List.ids"), n + 1, _rt.addr(m))
                _rt.put(items, n, -9223372036854775807 - 1)
            n += 1
        i += 1
    _rt.set(l, "List.len", n)
    return l


# ---------- dicts: CPython's compact ordered layout (runtime.c's Dict) ----------
# The layout, the sizes and the hashes are described with runtime.c's dicts. Entries (keys,
# vals, hs) are kept in insertion order; idx is open addressing over the slots that hold an
# entry's number plus one, 0 where empty and -1 where deleted, as 32-bit words. This code
# keeps the table: the probes of int and str keys, insertion, deletion, the rebuilds, the
# copies and the loops' steps. runtime.c still hashes and compares the keys that a type
# descriptor describes (pys_rt_hobj, pys_rt_dfind_obj), whose __hash__ and __eq__ may run the
# program's code: after such a call this code reads the dict's fields again, as runtime.c did.
# A lookup's result is an idx slot, or below zero where the key is not there: -1 in a dict
# with no table, else -2 less the slot that an insertion of the key takes (the first hole or
# empty slot its probes met).


def pys_rt_hobj(kind: int, k: int) -> int: ...
def pys_rt_dfind_obj(d: _rt.Ptr, k: int, h: int) -> int: ...
def pys_rt_dict_keyerr(d: _rt.Ptr, k: int) -> None: ...
def pys_rt_probe() -> None: ...
def pys_big_box(v: int, m: _rt.Ptr) -> _rt.Ptr: ...


@_rt.unchecked
def int_key_hash(k: int) -> int:
    # a native int key's hash: 0 marks a hole
    h = pys_hash_int(k)
    return h if h != 0 else 1


@_rt.inline
@_rt.unchecked
def pys_rt_dhash(d: _rt.Ptr, k: int) -> int:
    # the hash of key k of d: kind 0 int keys, 1 str keys (2 on it: hashed by CPython's hash),
    # else by the descriptor of a tuple or object key
    kind = _rt.get(d, "Dict.kind")
    if kind & -3 == 1:
        return str_key_hash(k)
    if kind > 1:
        return pys_rt_hobj(kind, k)
    return int_key_hash(k)


@_rt.unchecked
def dict_mask(d: _rt.Ptr) -> int:
    # idx's slots, less one: CPython's size where the keys are hashed by CPython's hash, else twice
    size = _rt.get(d, "Dict.size")
    return (size if _rt.get(d, "Dict.kind") & 2 != 0 else size * 2) - 1


@_rt.unchecked
def dict_step(i: int, p: int, m: int) -> int:
    # CPython's next probe: each step mixes five more of the hash's bits in (p: what is left)
    return _rt.wrap_add(_rt.wrap_add(_rt.wrap_mul(i, 5), p), 1) & m


@_rt.unchecked
def pys_rt_dbig(d: _rt.Ptr, e: int) -> _rt.Ptr:
    # the Mpz of entry e's value where it is an int past 64 bits (its slot holds -2**63), else null
    if not _rt.null(_rt.getp(d, "Dict.vb")) and _rt.word(_rt.getp(d, "Dict.vals"), e) == -9223372036854775807 - 1 and pys_rt_opt_in() != 0:
        return _rt.ptr(_rt.word(_rt.getp(d, "Dict.vb"), e))
    return _rt.nil()


@_rt.unchecked
def dict_val_clear(d: _rt.Ptr, e: int) -> None:
    # every store of a value clears its entry's Mpz word
    if not _rt.null(_rt.getp(d, "Dict.vb")):
        _rt.put(_rt.getp(d, "Dict.vb"), e, 0)


@_rt.unchecked
def dict_key_clear(d: _rt.Ptr, e: int) -> None:
    if not _rt.null(_rt.getp(d, "Dict.kb")):
        _rt.put(_rt.getp(d, "Dict.kb"), e, 0)


@_rt.unchecked
def pys_rt_dbig_make(d: _rt.Ptr) -> None:
    # the array of the values' Mpz words, as long as the entries', which the first one makes
    if _rt.null(_rt.getp(d, "Dict.vb")):
        _rt.setp(d, "Dict.vb", pys_alloc(_rt.udiv(_rt.get(d, "Dict.size") * 2, 3) * 8))


@_rt.noinline
@_rt.unchecked
def dict_find_int(d: _rt.Ptr, k: int, h: int, m: int) -> int:
    # the probes for native int key k, whose hash is h, over idx's m + 1 slots: such a table
    # meets no str and no entry of a key past 64 bits with the hash of a 64-bit one. A function
    # of its own, as the str keys' is: the entry points call it with the lookup's state in
    # registers, and the compiler's every dict use does not carry a copy of the loop
    idx = _rt.getp(d, "Dict.idx")
    hs = _rt.getp(d, "Dict.hs")
    keys = _rt.getp(d, "Dict.keys")
    f = -1
    i = h & m
    p = h
    while True:
        pys_rt_probe()
        e = _rt.i32_at(idx, i)
        if e == 0:
            return -2 - (i if f < 0 else f)
        if e < 0:
            if f < 0:
                f = i
        elif _rt.word(hs, e - 1) == h and _rt.word(keys, e - 1) == k:
            return i
        p = _rt.lshr(p, 5)
        i = dict_step(i, p, m)
    return -1  # (not reached)


@_rt.noinline
@_rt.unchecked
def dict_find_str(d: _rt.Ptr, k: int, h: int, m: int) -> int:
    # and for a str key: a str keeps its hash, so it is compared before the keys are read
    idx = _rt.getp(d, "Dict.idx")
    hs = _rt.getp(d, "Dict.hs")
    keys = _rt.getp(d, "Dict.keys")
    f = -1
    i = h & m
    p = h
    while True:
        pys_rt_probe()
        e = _rt.i32_at(idx, i)
        if e == 0:
            return -2 - (i if f < 0 else f)
        if e < 0:
            if f < 0:
                f = i
        elif _rt.word(hs, e - 1) == h:
            x = _rt.word(keys, e - 1)
            if x == k or same_str(x, k):
                return i
        p = _rt.lshr(p, 5)
        i = dict_step(i, p, m)
    return -1  # (not reached)


@_rt.inline
@_rt.unchecked
def pys_rt_dfind(d: _rt.Ptr, k: int, h: int) -> int:
    # k's idx slot, or below zero (see above), for a key whose hash h its caller has: an
    # entry's stored one
    size = _rt.get(d, "Dict.size")
    if size == 0:
        return -1
    kind = _rt.get(d, "Dict.kind")
    if kind & -3 == 1:
        return dict_find_str(d, k, h, (size if kind & 2 != 0 else size * 2) - 1)
    if kind > 1:
        return pys_rt_dfind_obj(d, k, h)
    return dict_find_int(d, k, h, size * 2 - 1)


@_rt.inline
@_rt.unchecked
def dict_slot(d: _rt.Ptr, k: int) -> int:
    # k's idx slot, or below zero: one hash and one lookup. Each kind of key hashes and then
    # calls its own probe, as runtime.c's dhfind did: one test of the kind for both. (A hash
    # of the program's may give d its first table: the size is read after it, and runtime.c's
    # probe reads the kind's mark itself)
    kind = _rt.get(d, "Dict.kind")
    if kind & -3 == 1:
        h = str_key_hash(k)
        size = _rt.get(d, "Dict.size")
        if size == 0:
            return -1
        return dict_find_str(d, k, h, (size if kind & 2 != 0 else size * 2) - 1)
    if kind > 1:
        h = pys_rt_hobj(kind, k)
        if _rt.get(d, "Dict.size") == 0:
            return -1
        return pys_rt_dfind_obj(d, k, h)
    size = _rt.get(d, "Dict.size")
    if size == 0:
        return -1
    return dict_find_int(d, k, int_key_hash(k), size * 2 - 1)


@_rt.unchecked
def pys_rt_dbfind(d: _rt.Ptr, m: _rt.Ptr, h: int) -> int:
    # the same for key m, an int past 64 bits whose hash is h: an entry of that hash whose
    # key's Mpz is equal to m
    if _rt.get(d, "Dict.size") == 0:
        return -1
    idx = _rt.getp(d, "Dict.idx")
    hs = _rt.getp(d, "Dict.hs")
    k = dict_mask(d)
    f = -1
    i = h & k
    p = h
    while True:
        pys_rt_probe()
        e = _rt.i32_at(idx, i)
        if e == 0:
            return -2 - (i if f < 0 else f)
        if e < 0:
            if f < 0:
                f = i
        elif _rt.word(hs, e - 1) == h:
            x = dict_key_big(d, e - 1)
            if not _rt.null(x) and (x is m or pys_mpz_cmp(x, m) == 0):
                return i
        p = _rt.lshr(p, 5)
        i = dict_step(i, p, k)
    return -1  # (not reached)


@_rt.unchecked
def pys_rt_dempty(d: _rt.Ptr, h: int) -> int:
    # find_empty_slot: hash h's first idx slot that is a hole or empty
    idx = _rt.getp(d, "Dict.idx")
    m = dict_mask(d)
    p = h
    i = p & m
    while True:
        pys_rt_probe()
        if _rt.i32_at(idx, i) <= 0:
            return i
        p = _rt.lshr(p, 5)
        i = dict_step(i, p, m)
    return -1  # (not reached)


@_rt.inline
@_rt.unchecked
def pys_rt_dslot(d: _rt.Ptr, e: int) -> int:
    # the idx slot of live entry e, found by its position (CPython's lookdict_index), not its key
    idx = _rt.getp(d, "Dict.idx")
    m = dict_mask(d)
    p = _rt.word(_rt.getp(d, "Dict.hs"), e)
    i = p & m
    pys_rt_probe()
    while _rt.i32_at(idx, i) != e + 1:
        p = _rt.lshr(p, 5)
        i = dict_step(i, p, m)
        pys_rt_probe()
    return i


@_rt.unchecked
def pys_rt_keysize(n: int) -> int:
    # calculate_log2_keysize: the first power of two, from 8, that is not below n
    s = 8
    while s < n:
        s = s * 2
    return s


@_rt.unchecked
def pys_rt_dbuild(d: _rt.Ptr, src: _rt.Ptr, size: int) -> None:
    # d := src's items in a table of this size, holes dropped (d may be src). A table's first
    # build marks a dict whose keys are hashed by CPython's hash (2 on its kind)
    if pys_rt_khash(_rt.get(d, "Dict.kind")) != 0:
        _rt.set(d, "Dict.kind", _rt.get(d, "Dict.kind") | 2)
    u = _rt.udiv(size * 2, 3)
    k = pys_rt_keymem(_rt.get(d, "Dict.kind"), u)
    v = item_array(u, _rt.get(d, "Dict.vatomic"))
    m = (size if _rt.get(d, "Dict.kind") & 2 != 0 else size * 2) - 1
    vb = _rt.nil()
    if not _rt.null(_rt.getp(src, "Dict.vb")):
        vb = pys_alloc(u * 8)
    kb = _rt.nil()
    if not _rt.null(_rt.getp(src, "Dict.kb")):
        kb = pys_alloc(u * 8)
    hs = pys_alloc_atomic(u * 8)
    ix = pys_alloc_atomic((m + 1) * 4)
    sn = _rt.get(src, "Dict.n")
    sk = _rt.getp(src, "Dict.keys")
    sv = _rt.getp(src, "Dict.vals")
    sh = _rt.getp(src, "Dict.hs")
    if not _rt.null(vb) or not _rt.null(kb):
        # (the live entries' Mpz words, in their new order: a pass of its own)
        e = 0
        j = 0
        while e < sn:
            if dict_live(src, e):
                if not _rt.null(vb):
                    _rt.put(vb, j, _rt.word(_rt.getp(src, "Dict.vb"), e))
                if not _rt.null(kb):
                    _rt.put(kb, j, _rt.word(_rt.getp(src, "Dict.kb"), e))
                j += 1
            e += 1
    n = 0
    e = 0
    while e < sn:
        if dict_live(src, e):
            h = _rt.word(sh, e)
            p = h
            i = p & m
            pys_rt_probe()
            while _rt.i32_at(ix, i) != 0:
                p = _rt.lshr(p, 5)
                i = dict_step(i, p, m)
                pys_rt_probe()
            _rt.put(k, n, _rt.word(sk, e))
            _rt.put(v, n, _rt.word(sv, e))
            _rt.put(hs, n, h)
            n += 1
            _rt.put_i32(ix, i, n)
        e += 1
    _rt.set(d, "Dict.len", n)
    _rt.set(d, "Dict.n", n)
    _rt.set(d, "Dict.cut", 0)
    _rt.set(d, "Dict.size", size)
    _rt.setp(d, "Dict.keys", k)
    _rt.setp(d, "Dict.vals", v)
    _rt.setp(d, "Dict.hs", hs)
    _rt.setp(d, "Dict.idx", ix)
    _rt.setp(d, "Dict.vb", vb)
    _rt.setp(d, "Dict.kb", kb)


@_rt.unchecked
def dict_make(kind: int, n: int, vatomic: int) -> _rt.Ptr:
    # a display of n items is presized, as in CPython. (The allocator adds its byte of slack:
    # the header keeps 96 bytes)
    d = pys_alloc(_rt.sizeof("Dict") - 1)
    _rt.set(d, "Dict.kind", kind)
    _rt.set(d, "Dict.vatomic", vatomic)
    if n > 5:
        pys_rt_dbuild(d, d, 131072 if n > 87381 else pys_rt_keysize(_rt.udiv(n * 3 + 1, 2)))
    return d


def pys_dict_new(kind: int, n: int) -> _rt.Ptr:
    return dict_make(kind, n, 0)


def pys_dict_new_atomic(kind: int, n: int) -> _rt.Ptr:
    # a dict of int, float or bool values, which the compiler makes with this: the arrays of its
    # values are atomic, and so are those of its copies (dict.copy(), dict(d)); dict.fromkeys and
    # the empty dicts that a template returns while their type is open are made by pys_dict_new
    return dict_make(kind, n, 1)


@_rt.inline
@_rt.unchecked
def dict_entry(d: _rt.Ptr, k: int) -> int:
    # k's entry, or -1
    i = dict_slot(d, k)
    if i < 0:
        return -1
    return _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1


# The entry points that hash a key stay calls in a program's AOT build (@_rt.noinline), as the
# sets' do: copied into every lookup of the compiler, they made its executable 14% larger and
# its AOT build 16% longer, for 1-2% of speed on dict benchmarks.


@_rt.noinline
@_rt.unchecked
def pys_dict_has(d: _rt.Ptr, k: int) -> int:
    return 1 if dict_entry(d, k) >= 0 else 0


@_rt.noinline
@_rt.unchecked
def pys_dict_getitem(d: _rt.Ptr, k: int) -> int:
    e = dict_entry(d, k)
    if e < 0:
        pys_rt_dict_keyerr(d, k)
    return _rt.word(_rt.getp(d, "Dict.vals"), e)


@_rt.noinline
@_rt.unchecked
def pys_dict_find(d: _rt.Ptr, k: int) -> int:
    # one lookup where a has or a getitem of a key comes before a getitem or a set of it, and
    # no dict changes between (the compiler's dictfuse): k's entry, or -1 (find) or a KeyError
    # (entry); pys_dict_val reads that entry's value, and entry_set writes it as pys_dict_set
    # overwrites one, which moves no entry
    return dict_entry(d, k)


@_rt.noinline
@_rt.unchecked
def pys_dict_eq_find(d: _rt.Ptr, source: _rt.Ptr, e: int) -> int:
    # Equality reuses the source entry's stored hash: rerunning __hash__ here would add effects
    # and could hide a key whose hash changed since insertion. The source key/value can disappear
    # during lookup; snapshot its key/hash before the lookup, which restarts when a callback
    # changes the target table
    k = _rt.word(_rt.getp(source, "Dict.keys"), e)
    h = _rt.word(_rt.getp(source, "Dict.hs"), e)
    m = dict_key_big(source, e)
    i = pys_rt_dfind(d, k, h) if _rt.null(m) else pys_rt_dbfind(d, m, h)
    if i < 0:
        return -1
    return _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1


@_rt.noinline
@_rt.unchecked
def pys_dict_entry(d: _rt.Ptr, k: int) -> int:
    e = dict_entry(d, k)
    if e < 0:
        pys_rt_dict_keyerr(d, k)
    return e


@_rt.unchecked
def pys_dict_entry_set(d: _rt.Ptr, e: int, v: int) -> None:
    _rt.put(_rt.getp(d, "Dict.vals"), e, v)
    dict_val_clear(d, e)


@_rt.unchecked
def pys_dict_entry_set_big(d: _rt.Ptr, e: int, lo: int, m: _rt.Ptr) -> None:
    # entry_set of a promoting int (pys_dict_set_big)
    if _rt.null(m):
        pys_dict_entry_set(d, e, lo)
        return
    _rt.put(_rt.getp(d, "Dict.vals"), e, -9223372036854775807 - 1)
    pys_rt_dbig_make(d)
    _rt.put(_rt.getp(d, "Dict.vb"), e, _rt.addr(m))


@_rt.noinline
@_rt.unchecked
def pys_dict_get(d: _rt.Ptr, k: int, dflt: int) -> int:
    e = dict_entry(d, k)
    return dflt if e < 0 else _rt.word(_rt.getp(d, "Dict.vals"), e)


@_rt.noinline
@_rt.unchecked
def dict_grow(d: _rt.Ptr, h: int) -> int:
    # insertion_resize: hash h's idx slot in the larger table
    pys_rt_dbuild(d, d, pys_rt_keysize(_rt.get(d, "Dict.len") * 3))
    return pys_rt_dempty(d, h)


@_rt.inline
@_rt.unchecked
def pys_rt_dfull(d: _rt.Ptr) -> int:
    # is the table full: used >= floor(2 * size / 3), without dividing on each insertion
    # (popitem's entries, which it cuts off the end, still count). As unsigned ints, whose
    # products fit for every size a table may have (a power of two, at most 2**62) and for none
    used = _rt.wrap_add(_rt.wrap_mul(_rt.get(d, "Dict.n") + _rt.get(d, "Dict.cut"), 3), 2)
    return 1 if _rt.ule(_rt.wrap_mul(_rt.get(d, "Dict.size"), 2), used) else 0


@_rt.inline
@_rt.unchecked
def pys_rt_dadd(d: _rt.Ptr, k: int, h: int, v: int, r: int) -> None:
    # k, which d has not, into the idx slot that its lookup's result r names; a full table is
    # rebuilt first. Both Mpz words of the new entry are null already: allocation zeroes them,
    # and deletion and popitem clear them before an entry can be used again
    f = -2 - r
    if pys_rt_dfull(d) != 0:
        f = dict_grow(d, h)
    n = _rt.get(d, "Dict.n")
    _rt.put(_rt.getp(d, "Dict.keys"), n, k)
    _rt.put(_rt.getp(d, "Dict.vals"), n, v)
    _rt.put(_rt.getp(d, "Dict.hs"), n, h)
    _rt.put_i32(_rt.getp(d, "Dict.idx"), f, n + 1)
    _rt.set(d, "Dict.n", n + 1)
    _rt.set(d, "Dict.len", _rt.get(d, "Dict.len") + 1)


@_rt.unchecked
def pys_rt_dset(d: _rt.Ptr, k: int, h: int, v: int) -> int:
    # d[k] = v, k's hash h: the entry
    i = pys_rt_dfind(d, k, h)
    if i >= 0:
        e = _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1
        _rt.put(_rt.getp(d, "Dict.vals"), e, v)
        dict_val_clear(d, e)
        return e
    pys_rt_dadd(d, k, h, v, i)
    return _rt.get(d, "Dict.n") - 1


@_rt.inline
@_rt.unchecked
def dict_put(d: _rt.Ptr, k: int, v: int, how: int) -> int:
    # one hash and one lookup of k, then a store. how 0: d[k] = v, and the entry; 1:
    # d.setdefault(k, v), and the value there, v where it was stored; 2: k's entry, added with
    # the value v where d has none. Each kind of key hashes and then calls its own probe (see
    # dict_slot); how is a constant of each caller, which keeps its own case
    kind = _rt.get(d, "Dict.kind")
    if kind & -3 == 1:
        h = str_key_hash(k)
        size = _rt.get(d, "Dict.size")
        i = -1
        if size != 0:
            i = dict_find_str(d, k, h, (size if kind & 2 != 0 else size * 2) - 1)
    elif kind > 1:
        h = pys_rt_hobj(kind, k)
        i = -1
        if _rt.get(d, "Dict.size") != 0:
            i = pys_rt_dfind_obj(d, k, h)
    else:
        h = int_key_hash(k)
        size = _rt.get(d, "Dict.size")
        i = -1
        if size != 0:
            i = dict_find_int(d, k, h, size * 2 - 1)
    if i >= 0:
        e = _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1
        if how == 1:
            return _rt.word(_rt.getp(d, "Dict.vals"), e)
        if how == 0:
            _rt.put(_rt.getp(d, "Dict.vals"), e, v)
            dict_val_clear(d, e)
        return e
    pys_rt_dadd(d, k, h, v, i)
    return v if how == 1 else _rt.get(d, "Dict.n") - 1


@_rt.noinline
@_rt.unchecked
def pys_dict_set(d: _rt.Ptr, k: int, v: int) -> None:
    dict_put(d, k, v, 0)


@_rt.noinline
@_rt.unchecked
def pys_dict_set_big(d: _rt.Ptr, k: int, lo: int, m: _rt.Ptr) -> None:
    # d[k] = {lo, m}, a promoting int: past 64 bits, -2**63 and its Mpz
    if _rt.null(m):
        pys_dict_set(d, k, lo)
        return
    e = dict_put(d, k, -9223372036854775807 - 1, 0)
    pys_rt_dbig_make(d)
    _rt.put(_rt.getp(d, "Dict.vb"), e, _rt.addr(m))


@_rt.unchecked
def pys_rt_dbadd(d: _rt.Ptr, m: _rt.Ptr, h: int, v: int, r: int) -> int:
    # d[k] = v of key k past 64 bits, its Mpz m, whose hash is h and which d has not: its entry
    pys_rt_dadd(d, -9223372036854775807 - 1, h, v, r)
    if _rt.null(_rt.getp(d, "Dict.kb")):
        _rt.setp(d, "Dict.kb", pys_alloc(_rt.udiv(_rt.get(d, "Dict.size") * 2, 3) * 8))
    e = _rt.get(d, "Dict.n") - 1
    _rt.put(_rt.getp(d, "Dict.kb"), e, _rt.addr(m))
    return e


@_rt.unchecked
def pys_rt_dbput(d: _rt.Ptr, m: _rt.Ptr, h: int, v: int) -> int:
    i = pys_rt_dbfind(d, m, h)
    if i >= 0:
        e = _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1
        _rt.put(_rt.getp(d, "Dict.vals"), e, v)
        dict_val_clear(d, e)
        return e
    return pys_rt_dbadd(d, m, h, v, i)


@_rt.unchecked
def dict_hole(d: _rt.Ptr, e: int) -> None:
    # entry e becomes a hole: a table hashed by CPython's hash keeps -1 for its hash, another 0
    _rt.put(_rt.getp(d, "Dict.hs"), e, -1 if _rt.get(d, "Dict.kind") & 2 != 0 else 0)
    _rt.put(_rt.getp(d, "Dict.keys"), e, 0)
    _rt.put(_rt.getp(d, "Dict.vals"), e, 0)
    dict_val_clear(d, e)
    dict_key_clear(d, e)
    _rt.set(d, "Dict.len", _rt.get(d, "Dict.len") - 1)


@_rt.inline
@_rt.unchecked
def pys_rt_dtake(d: _rt.Ptr, i: int) -> int:
    # the value of the entry in idx slot i, which is deleted
    idx = _rt.getp(d, "Dict.idx")
    e = _rt.i32_at(idx, i) - 1
    v = _rt.word(_rt.getp(d, "Dict.vals"), e)
    _rt.put_i32(idx, i, -1)
    dict_hole(d, e)
    return v


@_rt.inline
@_rt.unchecked
def pys_rt_dpfind(d: _rt.Ptr, k: int) -> int:
    # d.pop(k)'s lookup, as CPython's dict_pop, which does not hash k where d is empty; del d[k]
    # (pys_dict_del) hashes it first, as PyDict_DelItem. Only a class's __hash__ can tell them
    # apart (kind > 1): the compiler calls pys_dict_pop for del of other keys
    kind = _rt.get(d, "Dict.kind")
    size = _rt.get(d, "Dict.size")
    if kind == 1:
        if size == 0:
            return -1
        return dict_find_str(d, k, str_key_hash(k), size * 2 - 1)
    if kind > 1:
        if _rt.get(d, "Dict.len") == 0:
            return -1
        return dict_slot(d, k)
    if size == 0:
        return -1
    return dict_find_int(d, k, int_key_hash(k), size * 2 - 1)


@_rt.unchecked
def pys_dict_pop(d: _rt.Ptr, k: int) -> int:
    i = pys_rt_dpfind(d, k)
    if i < 0:
        pys_rt_dict_keyerr(d, k)
    return pys_rt_dtake(d, i)


@_rt.unchecked
def pys_dict_pop_default(d: _rt.Ptr, k: int, dflt: int) -> int:
    i = pys_rt_dpfind(d, k)
    if i < 0:
        return dflt
    return pys_rt_dtake(d, i)


@_rt.inline
@_rt.unchecked
def dict_pair(d: _rt.Ptr, e: int, big: int) -> _rt.Ptr:
    # entry e's (key, value) tuple; big: of promoting ints, whose key or value past 64 bits
    # holds -2**63 and its Mpz in slot 2 or 3, else of 64-bit ints. (That tuple is one of
    # promoting ints too, where neither slot holds -2**63: only there is an Mpz word read)
    k = _rt.word(_rt.getp(d, "Dict.keys"), e)
    v = _rt.word(_rt.getp(d, "Dict.vals"), e)
    if big != 0 and (k == -9223372036854775807 - 1 or v == -9223372036854775807 - 1):
        t = pys_alloc(32)
        _rt.put(t, 2, _rt.addr(dict_key_big(d, e)))
        _rt.put(t, 3, _rt.addr(pys_rt_dbig(d, e)))
    else:
        t = pys_alloc(16)
    _rt.put(t, 0, _rt.word(_rt.getp(d, "Dict.keys"), e))
    _rt.put(t, 1, _rt.word(_rt.getp(d, "Dict.vals"), e))
    return t


@_rt.inline
@_rt.unchecked
def dict_popitem(d: _rt.Ptr, big: int) -> _rt.Ptr:
    # d.popitem() (dict_popitem_impl): the last entry's (key, value) tuple. The entries end
    # where it was, as CPython sets dk_nentries, so the holes before it are not walked again:
    # popping every item takes linear time. Its idx slot is found by its position, not its key,
    # and stays deleted, so the entries cut off still fill the table until it is rebuilt (CPython
    # does not give dk_usable back): otherwise inserts after pops would use up its empty slots
    if _rt.get(d, "Dict.len") == 0:
        _rt.fail("KeyError", "'popitem(): dictionary is empty'")
    e = _rt.get(d, "Dict.n") - 1
    while not dict_live(d, e):  # (a class's key may hash to 0: see dict_live)
        e -= 1
    if big == 0 and (not _rt.null(pys_rt_dbig(d, e)) or not _rt.null(dict_key_big(d, e))):
        raise OverflowError("Python int too large to convert to C long")
    i = pys_rt_dslot(d, e)
    t = dict_pair(d, e, big)
    _rt.put_i32(_rt.getp(d, "Dict.idx"), i, -1)
    dict_hole(d, e)
    _rt.set(d, "Dict.cut", _rt.get(d, "Dict.cut") + _rt.get(d, "Dict.n") - e)
    _rt.set(d, "Dict.n", e)
    return t


def pys_dict_popitem(d: _rt.Ptr) -> _rt.Ptr:
    return dict_popitem(d, 0)


def pys_dict_big_popitem(d: _rt.Ptr) -> _rt.Ptr:
    # (of a dict of ints or of int keys)
    return dict_popitem(d, 1)


@_rt.unchecked
def pys_dict_del(d: _rt.Ptr, k: int) -> int:
    i = dict_slot(d, k)
    if i < 0:
        pys_rt_dict_keyerr(d, k)
    return pys_rt_dtake(d, i)


@_rt.unchecked
def pys_dict_entry_del(d: _rt.Ptr, e: int) -> None:
    # A preceding lookup found this entry; no user operation occurs between that lookup and
    # deletion. Its idx slot is found without hashing or comparing the key again
    pys_rt_dtake(d, pys_rt_dslot(d, e))


@_rt.unchecked
def dict_take_big(d: _rt.Ptr, i: int) -> tuple[int, _rt.Ptr]:
    # the promoting int of the entry in idx slot i, which is deleted
    b = pys_rt_dbig(d, _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1)
    v = pys_rt_dtake(d, i)
    return (v if _rt.null(b) else 0), b


@_rt.unchecked
def dict_value_big(d: _rt.Ptr, i: int) -> tuple[int, _rt.Ptr]:
    # and of the entry in idx slot i, which stays
    e = _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1
    b = pys_rt_dbig(d, e)
    return (_rt.word(_rt.getp(d, "Dict.vals"), e) if _rt.null(b) else 0), b


@_rt.unchecked
def pys_dict_big_pop(d: _rt.Ptr, k: int, has: int, lo: int, m: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    # d.pop(k) (has: d.pop(k, {lo, m})) of a dict of ints, whose value may be past 64 bits: the
    # promoting int, by value
    i = pys_rt_dpfind(d, k)
    if i < 0:
        if has == 0:
            pys_rt_dict_keyerr(d, k)
        return lo, m
    v, b = dict_take_big(d, i)
    return v, b


@_rt.noinline
@_rt.unchecked
def pys_dict_big_setdefault(d: _rt.Ptr, k: int, lo: int, m: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    # d.setdefault(k, {lo, m}): one hash and one lookup, as CPython's
    h = pys_rt_dhash(d, k)
    i = pys_rt_dfind(d, k, h)
    if i >= 0:
        v, b = dict_value_big(d, i)
        return v, b
    pys_rt_dadd(d, k, h, lo if _rt.null(m) else -9223372036854775807 - 1, i)
    if not _rt.null(m):
        pys_rt_dbig_make(d)
        _rt.put(_rt.getp(d, "Dict.vb"), _rt.get(d, "Dict.n") - 1, _rt.addr(m))
    return lo, m


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_big_pop(d: _rt.Ptr, klo: int, km: _rt.Ptr, has: int, lo: int, m: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    # the same by a promoting int key {klo, km}: one that fits as theirs; past 64 bits, by its Mpz
    if _rt.null(km):
        v, b = pys_dict_big_pop(d, klo, has, lo, m)
        return v, b
    i = pys_rt_dbfind(d, km, pys_rt_hbig(d, km))
    if i < 0:
        if has == 0:
            pys_rt_bkeyerr(km)
        return lo, m
    v, b = dict_take_big(d, i)
    return v, b


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_big_setdefault(d: _rt.Ptr, klo: int, km: _rt.Ptr, lo: int, m: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    if _rt.null(km):
        v, b = pys_dict_big_setdefault(d, klo, lo, m)
        return v, b
    h = pys_rt_hbig(d, km)
    i = pys_rt_dbfind(d, km, h)
    if i >= 0:
        v, b = dict_value_big(d, i)
        return v, b
    e = pys_rt_dbadd(d, km, h, lo if _rt.null(m) else -9223372036854775807 - 1, i)
    if not _rt.null(m):
        pys_rt_dbig_make(d)
        _rt.put(_rt.getp(d, "Dict.vb"), e, _rt.addr(m))
    return lo, m


@_rt.noinline
@_rt.unchecked
def pys_dict_getbox(d: _rt.Ptr, k: int, dflt: int) -> int:
    # d.get(k) and d.pop(k, None) of int, float and bool values: the value's box, or dflt (None
    # or a box)
    e = dict_entry(d, k)
    if e < 0:
        return dflt
    return _rt.addr(pys_big_box(_rt.word(_rt.getp(d, "Dict.vals"), e), pys_rt_dbig(d, e)))


@_rt.noinline
@_rt.unchecked
def pys_dict_popbox(d: _rt.Ptr, k: int, dflt: int) -> int:
    i = pys_rt_dpfind(d, k)
    if i < 0:
        return dflt
    m = pys_rt_dbig(d, _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1)
    return _rt.addr(pys_big_box(pys_rt_dtake(d, i), m))


@_rt.noinline
@_rt.unchecked
def pys_dict_setdefault(d: _rt.Ptr, k: int, v: int) -> int:
    # one hash and one lookup, as CPython's
    return dict_put(d, k, v, 1)


@_rt.unchecked
def dict_has_big(d: _rt.Ptr) -> bool:
    # does d hold a value past 64 bits
    vb = _rt.getp(d, "Dict.vb")
    if not _rt.null(vb):
        e = 0
        while e < _rt.get(d, "Dict.n"):
            if _rt.word(vb, e) != 0 and dict_live(d, e):
                return True
            e += 1
    return False


@_rt.unchecked
def dict_has_big_key(d: _rt.Ptr) -> bool:
    # does d hold a key past 64 bits
    if dict_has_big_keys(d):
        kb = _rt.getp(d, "Dict.kb")
        e = 0
        while e < _rt.get(d, "Dict.n"):
            if _rt.word(kb, e) != 0 and dict_live(d, e):
                return True
            e += 1
    return False


def pys_dict_narrow(d: _rt.Ptr) -> None:
    # d's values for 64-bit code (items())
    if dict_has_big(d):
        raise OverflowError("Python int too large to convert to C long")


def pys_dict_clear(d: _rt.Ptr) -> None:
    _rt.set(d, "Dict.len", 0)
    _rt.set(d, "Dict.n", 0)
    _rt.set(d, "Dict.cut", 0)
    _rt.set(d, "Dict.size", 0)
    _rt.setp(d, "Dict.keys", _rt.nil())
    _rt.setp(d, "Dict.vals", _rt.nil())
    _rt.setp(d, "Dict.vb", _rt.nil())
    _rt.setp(d, "Dict.kb", _rt.nil())
    _rt.setp(d, "Dict.hs", _rt.nil())
    _rt.setp(d, "Dict.idx", _rt.nil())


# The entry of key {lo, m} of a dict of int keys, a promoting int (past 64 bits, its Mpz m):
# find's, or -1; entry's, or KeyError; put's, which adds the key with the value 0 where d has
# none (the compiler stores the value next: pys_dict_entry_set); and del d[k]


@_rt.unchecked
def pys_rt_hbig(d: _rt.Ptr, m: _rt.Ptr) -> int:
    # A key past 64 bits follows its table's hash scheme too: CPython's hash of it where the
    # table keeps CPython's hashes, else that hash mixed as an int key's is, which never is the
    # hash of the 64-bit key its slot's sentinel is
    h = pys_mpz_hash(m)
    return h if pys_rt_khash(_rt.get(d, "Dict.kind")) != 0 else int_key_hash(h)


@_rt.noinline
@_rt.unchecked
def pys_dict_big_find(d: _rt.Ptr, lo: int, m: _rt.Ptr) -> int:
    if _rt.null(m):
        return dict_entry(d, lo)
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        return -1
    return _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1


@_rt.noinline
@_rt.unchecked
def pys_dict_big_entry(d: _rt.Ptr, lo: int, m: _rt.Ptr) -> int:
    e = pys_dict_big_find(d, lo, m)
    if e < 0:
        if not _rt.null(m):
            pys_rt_bkeyerr(m)
        pys_rt_dict_keyerr(d, lo)
    return e


@_rt.noinline
@_rt.unchecked
def pys_dict_big_put(d: _rt.Ptr, lo: int, m: _rt.Ptr) -> int:
    if not _rt.null(m):
        return pys_rt_dbput(d, m, pys_rt_hbig(d, m), 0)
    return dict_put(d, lo, 0, 2)


@_rt.unchecked
def pys_dict_big_del(d: _rt.Ptr, lo: int, m: _rt.Ptr) -> None:
    if _rt.null(m):
        pys_dict_del(d, lo)
        return
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        pys_rt_bkeyerr(m)
    pys_rt_dtake(d, i)


# get(k), pop(k), setdefault(k, v) and their boxes, as the functions above without bkey_, of a
# dict of int keys and a promoting int key {lo, m}: one that fits as theirs; past 64 bits, by
# the idx slot its own probes find


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_get(d: _rt.Ptr, lo: int, m: _rt.Ptr, dflt: int) -> int:
    if _rt.null(m):
        return pys_dict_get(d, lo, dflt)
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        return dflt
    return _rt.word(_rt.getp(d, "Dict.vals"), _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1)


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_getbox(d: _rt.Ptr, lo: int, m: _rt.Ptr, dflt: int) -> int:
    if _rt.null(m):
        return pys_dict_getbox(d, lo, dflt)
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        return dflt
    e = _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1
    return _rt.addr(pys_big_box(_rt.word(_rt.getp(d, "Dict.vals"), e), pys_rt_dbig(d, e)))


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_pop(d: _rt.Ptr, lo: int, m: _rt.Ptr) -> int:
    if _rt.null(m):
        return pys_dict_pop(d, lo)
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        pys_rt_bkeyerr(m)
    return pys_rt_dtake(d, i)


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_pop_default(d: _rt.Ptr, lo: int, m: _rt.Ptr, dflt: int) -> int:
    if _rt.null(m):
        return pys_dict_pop_default(d, lo, dflt)
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        return dflt
    return pys_rt_dtake(d, i)


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_popbox(d: _rt.Ptr, lo: int, m: _rt.Ptr, dflt: int) -> int:
    if _rt.null(m):
        return pys_dict_popbox(d, lo, dflt)
    i = pys_rt_dbfind(d, m, pys_rt_hbig(d, m))
    if i < 0:
        return dflt
    b = pys_rt_dbig(d, _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1)
    return _rt.addr(pys_big_box(pys_rt_dtake(d, i), b))


@_rt.noinline
@_rt.unchecked
def pys_dict_bkey_setdefault(d: _rt.Ptr, lo: int, m: _rt.Ptr, v: int) -> int:
    if _rt.null(m):
        return pys_dict_setdefault(d, lo, v)
    h = pys_rt_hbig(d, m)
    i = pys_rt_dbfind(d, m, h)
    if i >= 0:
        return _rt.word(_rt.getp(d, "Dict.vals"), _rt.i32_at(_rt.getp(d, "Dict.idx"), i) - 1)
    pys_rt_dbadd(d, m, h, v, i)
    return v


# For loops: entry e's key and value; the next entry from e (reversed: the previous one), or -1
# at the end, failing like CPython's dict iterators when the dict changed meanwhile: used = len
# when the loop started, count = items produced so far. As in CPython 3.13, a reversed loop
# also ends at a position past the entries (a rebuild made the table smaller)


def pys_dict_key(d: _rt.Ptr, e: int) -> int:
    return _rt.word(_rt.getp(d, "Dict.keys"), e)


def pys_dict_val(d: _rt.Ptr, e: int) -> int:
    return _rt.word(_rt.getp(d, "Dict.vals"), e)


def pys_dict_val_or_zero(d: _rt.Ptr, e: int) -> int:
    # a found entry's value, or zero without touching storage
    return 0 if e < 0 else _rt.word(_rt.getp(d, "Dict.vals"), e)


def pys_dict_big_val(d: _rt.Ptr, e: int) -> _rt.Ptr:
    # the Mpz of entry e's value, where pys_dict_val gave -2**63
    return pys_rt_dbig(d, e)


def pys_dict_big_key(d: _rt.Ptr, e: int) -> _rt.Ptr:
    # and of its key, where pys_dict_key gave -2**63
    return dict_key_big(d, e)


def pys_dict_end(d: _rt.Ptr) -> int:
    return _rt.get(d, "Dict.n")


@_rt.unchecked
def pys_dict_eq_next(d: _rt.Ptr, e: int) -> int:
    # Equality walks current live entries after each value comparison. Unlike an iterator,
    # callbacks may clear or resize the dict without a mutation error
    n = _rt.get(d, "Dict.n")
    while e < n and not dict_live(d, e):
        e += 1
    return e if e < n else -1


@_rt.unchecked
def pys_dict_next(d: _rt.Ptr, e: int, used: int, count: int) -> int:
    if _rt.get(d, "Dict.len") != used:
        raise RuntimeError("dictionary changed size during iteration")
    n = _rt.get(d, "Dict.n")
    while e < n and not dict_live(d, e):
        e += 1
    if e >= n:
        return -1
    if count >= used:
        raise RuntimeError("dictionary keys changed during iteration")
    return e


@_rt.unchecked
def pys_dict_prev(d: _rt.Ptr, e: int, used: int, count: int) -> int:
    if _rt.get(d, "Dict.len") != used:
        raise RuntimeError("dictionary changed size during iteration")
    if e < 0 or e >= _rt.get(d, "Dict.n"):
        return -1
    while e >= 0 and not dict_live(d, e):
        e -= 1
    if e >= 0 and count >= used:
        raise RuntimeError("dictionary keys changed during iteration")
    return e


@_rt.unchecked
def dict_column(d: _rt.Ptr, vals: int) -> _rt.Ptr:
    # the keys or values in a list whose array is of their array's kind (an int key's: atomic);
    # an int past 64 bits, -2**63 in its slot, has its Mpz in the new list's companion
    a = _rt.getp(d, "Dict.vals") if vals != 0 else _rt.getp(d, "Dict.keys")
    b = _rt.getp(d, "Dict.vb") if vals != 0 else _rt.getp(d, "Dict.kb")
    l = pys_list_make(_rt.get(d, "Dict.len"), pys_rt_atomic_items(a))
    items = _rt.getp(l, "List.a")
    n = 0
    e = 0
    while e < _rt.get(d, "Dict.n"):
        if dict_live(d, e):
            x = _rt.word(a, e)
            if not _rt.null(b) and x == -9223372036854775807 - 1 and pys_rt_opt_in() != 0 and _rt.word(b, e) != 0:
                big_companion(l)
                _rt.put(_rt.getp(l, "List.ids"), n + 1, _rt.word(b, e))
            _rt.put(items, n, x)
            n += 1
        e += 1
    _rt.set(l, "List.len", n)
    return l


def pys_dict_keys(d: _rt.Ptr) -> _rt.Ptr:
    return dict_column(d, 0)


def pys_dict_values(d: _rt.Ptr) -> _rt.Ptr:
    return dict_column(d, 1)


@_rt.unchecked
def dict_pairs(d: _rt.Ptr, big: int) -> _rt.Ptr:
    l = pys_list_make(_rt.get(d, "Dict.len"), 0)
    n = 0
    e = 0
    while e < _rt.get(d, "Dict.n"):
        if dict_live(d, e):
            t = dict_pair(d, e, big)
            _rt.put(_rt.getp(l, "List.a"), n, _rt.addr(t))
            n += 1
            _rt.set(l, "List.len", n)
        e += 1
    return l


def pys_dict_items(d: _rt.Ptr) -> _rt.Ptr:
    # (a tuple's int is a 64-bit one here: and its values, pys_dict_narrow)
    if dict_has_big_key(d):
        raise OverflowError("Python int too large to convert to C long")
    return dict_pairs(d, 0)


def pys_dict_big_items(d: _rt.Ptr) -> _rt.Ptr:
    # and those of a dict of ints or of int keys, in a program whose lists hold promoting ints:
    # an int key or value past 64 bits has its Mpz word
    return dict_pairs(d, 1)


# Copies, as CPython 3.13 makes them, since their tables decide what a loop that changes the
# copy sees: dict(d) merges d into a new empty dict, which clones a table without holes that is
# not sparse (8 slots, or more items than USABLE_FRACTION(size / 2)) and otherwise inserts the
# items into a table sized for them (estimate_log2_keysize); dict.copy() clones a table with at
# most a third of holes, and otherwise merges the same way. Keys hashed by their class are
# inserted one by one (pys_dict_update), as CPython's insertdict, which runs __eq__ for each
# key of the same hash that its probes meet; other keys compare equal to none of the others


@_rt.unchecked
def pys_rt_dretable(r: _rt.Ptr, d: _rt.Ptr) -> None:
    # r := d's table, holes included (r's descriptor is d's)
    u = _rt.udiv(_rt.get(d, "Dict.size") * 2, 3)
    x = (dict_mask(d) + 1) * 4
    n = _rt.get(d, "Dict.n")
    _rt.set(r, "Dict.kind", _rt.get(r, "Dict.kind") | (_rt.get(d, "Dict.kind") & 2))
    _rt.setp(r, "Dict.keys", pys_rt_keymem(_rt.get(r, "Dict.kind"), u))
    _rt.setp(r, "Dict.vals", item_array(u, _rt.get(r, "Dict.vatomic")))
    _rt.setp(r, "Dict.hs", pys_alloc_atomic(u * 8))
    _rt.setp(r, "Dict.idx", pys_alloc_atomic(x))
    _rt.cpy(_rt.getp(r, "Dict.keys"), _rt.getp(d, "Dict.keys"), n * 8)
    _rt.cpy(_rt.getp(r, "Dict.vals"), _rt.getp(d, "Dict.vals"), n * 8)
    _rt.cpy(_rt.getp(r, "Dict.hs"), _rt.getp(d, "Dict.hs"), n * 8)
    _rt.cpy(_rt.getp(r, "Dict.idx"), _rt.getp(d, "Dict.idx"), x)
    _rt.set(r, "Dict.len", _rt.get(d, "Dict.len"))
    _rt.set(r, "Dict.n", n)
    _rt.set(r, "Dict.cut", _rt.get(d, "Dict.cut"))
    _rt.set(r, "Dict.size", _rt.get(d, "Dict.size"))
    vb = _rt.nil()
    if not _rt.null(_rt.getp(d, "Dict.vb")):
        vb = pys_alloc(u * 8)
        _rt.cpy(vb, _rt.getp(d, "Dict.vb"), n * 8)
    _rt.setp(r, "Dict.vb", vb)
    kb = _rt.nil()
    if not _rt.null(_rt.getp(d, "Dict.kb")):
        kb = pys_alloc(u * 8)
        _rt.cpy(kb, _rt.getp(d, "Dict.kb"), n * 8)
    _rt.setp(r, "Dict.kb", kb)


@_rt.unchecked
def pys_rt_dclean(d: _rt.Ptr) -> int:
    # a table without holes that is not sparse
    n = _rt.get(d, "Dict.len")
    size = _rt.get(d, "Dict.size")
    return 1 if n != 0 and n == _rt.get(d, "Dict.n") and (size == 8 or _rt.udiv(_rt.udiv(size, 2) * 2, 3) < n) else 0


@_rt.unchecked
def dict_clone(d: _rt.Ptr) -> _rt.Ptr:
    r = dict_make(_rt.get(d, "Dict.kind"), 0, _rt.get(d, "Dict.vatomic"))
    pys_rt_dretable(r, d)
    return r


@_rt.unchecked
def pys_dict_update(d: _rt.Ptr, o: _rt.Ptr) -> None:
    # d.update(o) of a dict of d's type, as CPython 3.13's dict_dict_merge: an empty d takes a
    # clone of o's table where dict(o) would, else d is resized once for both dicts' items (if o
    # has more than d's table could take), then o's items are inserted in order (with the hashes
    # o keeps)
    used = _rt.get(o, "Dict.len")
    if o is d or used == 0:
        return
    if _rt.get(d, "Dict.len") == 0 and pys_rt_dclean(o) != 0:
        pys_rt_dretable(d, o)
        return
    size = _rt.get(d, "Dict.size")
    if _rt.udiv((size if size != 0 else 8) * 2, 3) < used:
        pys_rt_dbuild(d, d, pys_rt_keysize(_rt.udiv((_rt.get(d, "Dict.len") + used) * 3 + 1, 2)))
    e = 0
    while e < _rt.get(o, "Dict.n"):
        if dict_live(o, e):
            m = pys_rt_dbig(o, e)
            k = dict_key_big(o, e)
            h = _rt.word(_rt.getp(o, "Dict.hs"), e)
            v = _rt.word(_rt.getp(o, "Dict.vals"), e)
            if _rt.null(k):
                f = pys_rt_dset(d, _rt.word(_rt.getp(o, "Dict.keys"), e), h, v)
            else:
                f = pys_rt_dbput(d, k, h, v)
            if not _rt.null(m):
                pys_rt_dbig_make(d)
                _rt.put(_rt.getp(d, "Dict.vb"), f, _rt.addr(m))
            # A key comparison can mutate o. Check after insertion, as dict_dict_merge does, so
            # a callback's own exception wins and value-only changes remain allowed
            if _rt.get(o, "Dict.len") != used:
                raise RuntimeError("dict mutated during update")
        e += 1


@_rt.unchecked
def pys_dict_from(d: _rt.Ptr) -> _rt.Ptr:
    if pys_rt_dclean(d) != 0:
        return dict_clone(d)
    r = dict_make(_rt.get(d, "Dict.kind"), 0, _rt.get(d, "Dict.vatomic"))
    if _rt.get(d, "Dict.kind") & 2 != 0:
        pys_dict_update(r, d)
    elif _rt.get(d, "Dict.len") != 0:
        pys_rt_dbuild(r, d, pys_rt_keysize(_rt.udiv(_rt.get(d, "Dict.len") * 3 + 1, 2)))
    return r


@_rt.unchecked
def pys_dict_copy(d: _rt.Ptr) -> _rt.Ptr:
    n = _rt.get(d, "Dict.len")
    if n != 0 and n >= _rt.udiv(_rt.get(d, "Dict.n") * 2, 3):
        return dict_clone(d)
    return pys_dict_from(d)


@_rt.unchecked
def pys_dict_update_pairs(d: _rt.Ptr, l: _rt.Ptr) -> None:
    # d.update(pairs) of a list of (key, value) tuples, and dict.fromkeys(keys, v) of a list:
    # one insertion per item, as PyDict_MergeFromSeq2 and _PyDict_FromKeys make them
    i = 0
    while i < _rt.get(l, "List.len"):
        t = _rt.ptr(_rt.word(_rt.getp(l, "List.a"), i))
        pys_dict_set(d, _rt.word(t, 0), _rt.word(t, 1))
        i += 1


@_rt.unchecked
def pys_dict_update_pairs_big(d: _rt.Ptr, l: _rt.Ptr, kj: int, vj: int) -> None:
    # and of such a list that a program's lists hold as tuples of promoting ints, into a dict
    # of ints or of int keys: kj (vj) says that the key (the value) is an int, whose Mpz past
    # 64 bits is in the tuple's slot 2 (3), read where its slot holds -2**63
    i = 0
    while i < _rt.get(l, "List.len"):
        t = _rt.ptr(_rt.word(_rt.getp(l, "List.a"), i))
        key = _rt.word(t, 0)
        val = _rt.word(t, 1)
        k = _rt.nil()
        if kj != 0 and key == -9223372036854775807 - 1:
            k = _rt.ptr(_rt.word(t, 2))
        m = _rt.nil()
        if vj != 0 and val == -9223372036854775807 - 1:
            m = _rt.ptr(_rt.word(t, 3))
        if not _rt.null(k):
            e = pys_rt_dbput(d, k, pys_rt_hbig(d, k), val)
            if not _rt.null(m):
                pys_rt_dbig_make(d)
                _rt.put(_rt.getp(d, "Dict.vb"), e, _rt.addr(m))
        elif not _rt.null(m):
            pys_dict_set_big(d, key, 0, m)
        else:
            pys_dict_set(d, key, val)
        i += 1


@_rt.cold
@_rt.unchecked
def dict_fromkeys_big(d: _rt.Ptr, l: _rt.Ptr, v: int) -> None:
    # of a list of ints that may hold one past 64 bits
    i = 0
    while i < _rt.get(l, "List.len"):
        m = pys_rt_lbig(l, i)
        if _rt.null(m):
            pys_dict_set(d, _rt.word(_rt.getp(l, "List.a"), i), v)
        else:
            pys_rt_dbput(d, m, pys_rt_hbig(d, m), v)
        i += 1


@_rt.unchecked
def pys_dict_fromkeys(kind: int, l: _rt.Ptr, v: int) -> _rt.Ptr:
    d = pys_dict_new(kind, 0)
    if not _rt.null(_rt.getp(l, "List.ids")) and pys_rt_opt_in() != 0:
        dict_fromkeys_big(d, l, v)  # (a path of its own, so that the others' loop stays as it was)
    else:
        i = 0
        while i < _rt.get(l, "List.len"):
            pys_dict_set(d, _rt.word(_rt.getp(l, "List.a"), i), v)
            i += 1
    return d


@_rt.unchecked
def pys_dict_fromkeys_dict(o: _rt.Ptr, v: int) -> _rt.Ptr:
    # dict.fromkeys(o, v) of a dict o: sized for o's keys at once, as dict_dict_fromkeys does
    d = pys_dict_new(_rt.get(o, "Dict.kind"), 0)
    pys_rt_dbuild(d, d, pys_rt_keysize(_rt.udiv(_rt.get(o, "Dict.len") * 3 + 1, 2)))
    e = 0
    while e < _rt.get(o, "Dict.n"):
        if dict_live(o, e):
            k = dict_key_big(o, e)
            h = _rt.word(_rt.getp(o, "Dict.hs"), e)
            if _rt.null(k):
                pys_rt_dset(d, _rt.word(_rt.getp(o, "Dict.keys"), e), h, v)
            else:
                pys_rt_dbput(d, k, h, v)
        e += 1
    return d


# ---------- repr, equality and ordering by a type descriptor ----------
# The compiler describes a value's static type with a descriptor, a str whose letters runtime.c
# lists (its "generic repr / equality / ordering" comment): i int, f float, s str, L<e> list,
# D<k><v> dict, T<n><e...> fixed tuple, V<e> counted tuple, ?<e> None or a value, U<n>:... a
# tagged union, R<n>: an edge back to an enclosing descriptor, O<id> an object, and so on. The
# walks read a descriptor from its bytes on (d, an address into them) and step past a part with
# desc_skip. runtime.c keeps what they ask of it: the marks of the reprs under way
# (pys_repr_enter), which an unwind clears; the program's own __eq__, ordering and __repr__
# (pys_obj_*); exceptions; dynamic values; an Mpz's digits and a float's text; the table of
# printable characters; and the errors whose text it formats without allocating.


def pys_repr_enter(p: _rt.Ptr) -> int: ...
def pys_repr_leave(p: _rt.Ptr) -> None: ...
def pys_obj_eq(c: int, a: int, b: int) -> int: ...
def pys_obj_cmp(c: int, op: int, a: int, b: int) -> int: ...
def pys_obj_repr(c: int, a: int, b: int) -> str: ...
def pys_exc_repr(e: _rt.Ptr) -> str: ...
def pys_exc_type(e: _rt.Ptr) -> str: ...
def pys_exc_id(e: _rt.Ptr) -> _rt.Ptr: ...
def pys_dyn_eq(a: _rt.Ptr, b: _rt.Ptr) -> int: ...
def pys_dyn_cmp(a: _rt.Ptr, b: _rt.Ptr, op: int) -> int: ...
def pys_rt_dyn_eqitem(a: _rt.Ptr, b: _rt.Ptr) -> int: ...
def pys_rt_mpz_digits(m: _rt.Ptr) -> _rt.Ptr: ...
def pys_rt_mpz_cmp_float(m: _rt.Ptr, x: float) -> int: ...
def pys_big_cmp(alo: int, ahi: _rt.Ptr, blo: int, bhi: _rt.Ptr) -> int: ...
def pys_str_float(x: float) -> str: ...
def pys_str_cmp(a: str, b: str) -> int: ...
def pys_rt_printable(c: int) -> int: ...
def pys_rt_rec_deep(cmp: int) -> None: ...
def pys_rt_digits_deep() -> None: ...
def pys_rt_order_error(op: int, ca: int, cb: int, ea: _rt.Ptr, eb: _rt.Ptr) -> None: ...
def pys_rt_eq_probe() -> None: ...
def pys_str(p: _rt.Ptr, n: int) -> str: ...


# ---- the growing text of a repr (runtime.c's Buf, which a caller keeps in its frame)


@_rt.noinline
@_rt.unchecked
def pys_rt_put(b: _rt.Ptr, s: _rt.Ptr, n: int) -> None:
    # n bytes at s onto b. Its bytes grow to twice and more, allocated by the collector unzeroed
    # (the bytes past Buf.n are never read); out of line, which keeps the walks small
    have = _rt.get(b, "Buf.n")
    if have + n > _rt.get(b, "Buf.cap"):
        c = _rt.get(b, "Buf.cap") * 2 + n + 64
        p = pys_rt_raw(c)
        if have != 0:
            _rt.cpy(p, _rt.getp(b, "Buf.p"), have)
        _rt.setp(b, "Buf.p", p)
        _rt.set(b, "Buf.cap", c)
    if n != 0:
        _rt.cpy(_rt.offset(_rt.getp(b, "Buf.p"), have), s, n)
        _rt.set(b, "Buf.n", have + n)


@_rt.unchecked
def put_text(b: _rt.Ptr, s: str) -> None:
    pys_rt_put(b, str_bytes(s), len(s))


@_rt.unchecked
def put_char(b: _rt.Ptr, c: int) -> None:
    have = _rt.get(b, "Buf.n")
    if have < _rt.get(b, "Buf.cap"):
        _rt.put_byte(_rt.getp(b, "Buf.p"), have, c)
        _rt.set(b, "Buf.n", have + 1)
        return
    w = _rt.words(1)
    _rt.put_byte(w, 0, c)
    pys_rt_put(b, w, 1)


@_rt.unchecked
def put_int(b: _rt.Ptr, v: int) -> None:
    # v's decimal digits, written from the last one into the frame (20 bytes and the sign at most)
    w = _rt.words(3)
    u = _rt.wrap_sub(0, v) if v < 0 else v
    i = 24
    while True:
        i -= 1
        _rt.put_byte(w, i, _rt.wrap_add(48, _rt.urem(u, 10)))
        u = _rt.udiv(u, 10)
        if u == 0:
            break
    if v < 0:
        i -= 1
        _rt.put_byte(w, i, 45)
    pys_rt_put(b, _rt.offset(w, i), 24 - i)


@_rt.unchecked
def put_digits(b: _rt.Ptr, m: _rt.Ptr) -> None:
    # an int past 64 bits: its Mpz's digits, or CPython's ValueError past 4300 of them
    s = pys_rt_mpz_digits(m)
    if _rt.null(s):
        pys_rt_digits_deep()
    put_text(b, _rt.as_str(s))


@_rt.unchecked
def buf_done(b: _rt.Ptr) -> str:
    return pys_str(_rt.getp(b, "Buf.p"), _rt.get(b, "Buf.n"))


@_rt.unchecked
def buf_open(b: _rt.Ptr) -> None:
    _rt.setp(b, "Buf.p", _rt.nil())
    _rt.set(b, "Buf.n", 0)
    _rt.set(b, "Buf.cap", 0)


# ---- descriptors


@_rt.unchecked
def desc_of(s: _rt.Ptr) -> _rt.Ptr:
    # the bytes of a descriptor that a Str holds
    return _rt.offset(s, _rt.sizeof("Str"))


def is_digit(c: int) -> bool:
    return c >= 48 and c <= 57


@_rt.unchecked
def desc_num(d: _rt.Ptr) -> int:
    # a count or tag that ':' ends (the compiler's descriptors)
    n = 0
    i = 0
    c = _rt.byte_at(d, 0)
    while is_digit(c):
        n = n * 10 + c - 48
        i += 1
        c = _rt.byte_at(d, i)
    return n


@_rt.unchecked
def desc_past_num(d: _rt.Ptr) -> _rt.Ptr:
    # and the bytes past its ':'
    i = 0
    while is_digit(_rt.byte_at(d, i)):
        i += 1
    return _rt.offset(d, i + 1)


@_rt.unchecked
def pys_rt_ocls(d: _rt.Ptr) -> int:
    # an object's class number: three digits, then those of an id of 1000 or more
    c = (_rt.byte_at(d, 0) - 48) * 100 + (_rt.byte_at(d, 1) - 48) * 10 + _rt.byte_at(d, 2) - 48
    i = 3
    while is_digit(_rt.byte_at(d, i)):
        c = c * 10 + _rt.byte_at(d, i) - 48
        i += 1
    return c


@_rt.unchecked
def pys_rt_skip(d: _rt.Ptr) -> _rt.Ptr:
    # the bytes past the descriptor at d. An edge (R) is a leaf; an object's id ends at a letter, at
    # the end or at the '.' that a union puts after a member's (which this takes)
    c = _rt.byte_at(d, 0)
    d = _rt.offset(d, 1)
    if c == ord("R"):
        return desc_past_num(d)
    if c == ord("O") or c == ord("P") or c == ord("H"):
        i = 3
        while is_digit(_rt.byte_at(d, i)):
            i += 1
        return _rt.offset(d, i + 1 if _rt.byte_at(d, i) == ord(".") else i)
    if c == ord("L") or c == ord("V") or c == ord("?") or c == ord("S") or c == ord("F"):
        return pys_rt_skip(d)
    if c == ord("D"):
        return pys_rt_skip(pys_rt_skip(d))
    if c == ord("T"):
        n = _rt.byte_at(d, 0) - 48
        d = _rt.offset(d, 1)
        while n > 0:
            d = pys_rt_skip(d)
            n -= 1
    elif c == ord("U"):
        n = desc_num(d)
        d = desc_past_num(d)
        while n > 0:
            d = pys_rt_skip(desc_past_num(d))
            n -= 1
    return d


@_rt.inline
@_rt.unchecked
def desc_next(d: _rt.Ptr) -> _rt.Ptr:
    # the bytes past the part at d: a one-letter part's here, which a tuple's items mostly are
    c = _rt.byte_at(d, 0)
    if c == ord("i") or c == ord("s") or c == ord("f") or c == ord("b") or c == ord("J"):
        return _rt.offset(d, 1)
    return pys_rt_skip(d)


@_rt.unchecked
def recdesc(d: _rt.Ptr) -> _rt.Ptr:
    # where an edge leads: the descriptor that its count of bytes back begins
    while _rt.byte_at(d, 0) == ord("R"):
        d = _rt.offset(d, 0 - desc_num(_rt.offset(d, 1)))
    return d


@_rt.unchecked
def pys_rt_utype(tag: int, d: _rt.Ptr) -> _rt.Ptr:
    # the descriptor of union d's member of program-wide tag tag, which the union covers
    n = desc_num(_rt.offset(d, 1))
    d = desc_past_num(_rt.offset(d, 1))
    while n > 0:
        if desc_num(d) == tag:
            return desc_past_num(d)
        d = pys_rt_skip(desc_past_num(d))
        n -= 1
    return d  # (not reached: the compiler's descriptor covers every tag)


@_rt.unchecked
def unbox(v: int, d: _rt.Ptr) -> int:
    # the value of a ?<d> that is not None: an int's, float's or bool's box holds it
    c = _rt.byte_at(d, 0)
    if c == ord("i") or c == ord("f") or c == ord("b"):
        return _rt.word(_rt.ptr(v), 0)
    return v


@_rt.unchecked
def jbig_hi(v: int) -> _rt.Ptr:
    # a promoting int's two words at v (J): the Mpz of one past 64 bits, else null
    if _rt.word(_rt.ptr(v), 0) == -9223372036854775807 - 1 and pys_rt_opt_in() != 0:
        return _rt.ptr(_rt.word(_rt.ptr(v), 1))
    return _rt.nil()


@_rt.unchecked
def jbig_lo(v: int) -> int:
    # and its 64-bit value, 0 where it has an Mpz
    return 0 if not _rt.null(jbig_hi(v)) else _rt.word(_rt.ptr(v), 0)


@_rt.unchecked
def tuple_item(t: _rt.Ptr, n: int, i: int, e: _rt.Ptr, w: _rt.Ptr) -> int:
    # item i of fixed tuple t of n items, of descriptor e: a promoting int's two words in w, its
    # Mpz from word n + i where its slot holds -2**63
    if _rt.byte_at(e, 0) != ord("J") or pys_rt_opt_in() == 0:
        return _rt.word(t, i)
    x = _rt.word(t, i)
    _rt.put(w, 0, x)
    _rt.put(w, 1, _rt.word(t, n + i) if x == -9223372036854775807 - 1 else 0)
    return _rt.addr(w)


@_rt.unchecked
def vtuple_items(t: _rt.Ptr) -> _rt.Ptr:
    return _rt.offset(t, _rt.sizeof("VTuple"))


@_rt.unchecked
def vtuple_same(x: _rt.Ptr, y: _rt.Ptr, i: int) -> bool:
    # are items i of counted tuples x and y one object, by their identity companions
    a = _rt.getp(x, "VTuple.ids")
    b = _rt.getp(y, "VTuple.ids")
    if _rt.null(a) or _rt.null(b):
        return False
    k = _rt.word(a, i + 1)
    return k != 0 and k == _rt.word(b, i + 1)


@_rt.unchecked
def kind_desc(kind: int) -> _rt.Ptr:
    # the key descriptor of a dict's kind above 1 (2 marks CPython's hash; 3 is str and bytes keys
    # by that hash), without the '!' that asks for it
    p = str_bytes("!s") if kind == 3 else desc_of(_rt.ptr(kind & -3))
    return _rt.offset(p, 1) if _rt.byte_at(p, 0) == ord("!") else p


@_rt.unchecked
def desc_text_eq(p: _rt.Ptr, q: _rt.Ptr) -> bool:
    # are the descriptors at p and q, to their ends, the same text
    i = 0
    while True:
        c = _rt.byte_at(p, i)
        if c != _rt.byte_at(q, i):
            return False
        if c == 0:
            return True
        i += 1
    return False  # (not reached)


@_rt.unchecked
def same_desc(x: _rt.Ptr, y: _rt.Ptr) -> bool:
    # are the parts at x and y the same descriptor
    n = _rt.addr(pys_rt_skip(x)) - _rt.addr(x)
    return n == _rt.addr(pys_rt_skip(y)) - _rt.addr(y) and _rt.cmp(x, y, n) == 0


# ---- repr


@_rt.unchecked
def u8_point(p: _rt.Ptr, n: int) -> int:
    # the character at p (n > 0 bytes left), as its code point times 8 plus its byte count: a
    # UTF-8 sequence as chr() writes it, else the one byte (runtime.c's u8char)
    c = _rt.byte_at(p, 0)
    k = 1 if c > 0xF4 else 4 if c >= 0xF0 else 3 if c >= 0xE0 else 2 if c >= 0xC2 else 1
    if k == 1 or k > n:
        return c * 8 + 1
    v = c & (0x7F >> k)
    i = 1
    while i < k:
        x = _rt.byte_at(p, i)
        if x & 0xC0 != 0x80:
            return c * 8 + 1
        v = v << 6 | (x & 0x3F)
        i += 1
    if v < (0x80 if k == 2 else 0x800 if k == 3 else 0x10000) or v > 0x10FFFF:
        return c * 8 + 1
    return v * 8 + k


@_rt.unchecked
def hex_digit(v: int) -> int:
    return 48 + v if v < 10 else 87 + v


@_rt.unchecked
def char_repr(t: _rt.Ptr, p: _rt.Ptr, left: int, q: int) -> int:
    # the character at p (left > 0 bytes) as CPython's unicode_repr writes it between quotes q,
    # into t (12 bytes): the bytes written, plus 256 times the bytes it takes at p. (runtime.c's
    # report of an uncaught exception has its own, resc, which asks nothing of runtime.py)
    k = u8_point(p, left)
    c = k >> 3
    n = (k & 7) << 8
    if c == q or c == 92:
        _rt.put_byte(t, 0, 92)
        _rt.put_byte(t, 1, c)
        return 2 + n
    if c == 10 or c == 13 or c == 9:
        _rt.put_byte(t, 0, 92)
        _rt.put_byte(t, 1, ord("n") if c == 10 else ord("r") if c == 13 else ord("t"))
        return 2 + n
    if c < 32 or c == 127 or (c > 127 and pys_rt_printable(c) == 0):
        # not printable: \xhh, \uhhhh or \Uhhhhhhhh
        w = 2 if c < 0x100 else 4 if c < 0x10000 else 8
        _rt.put_byte(t, 0, 92)
        _rt.put_byte(t, 1, ord("x") if w == 2 else ord("u") if w == 4 else ord("U"))
        j = 0
        while j < w:
            _rt.put_byte(t, 2 + j, hex_digit(c >> (4 * (w - 1 - j)) & 15))
            j += 1
        return 2 + w + n
    _rt.cpy(t, p, k & 7)
    return (k & 7) + n


@_rt.noinline
@_rt.unchecked
def printable_run(p: _rt.Ptr, left: int, q: int) -> int:
    # The bytes of the printable characters from p on (left > 0 bytes, the first not ASCII) that
    # repr() copies as they are: all but the quote q and the backslash. A character of two or
    # three bytes is read here as u8_point reads it, and steps by that count, not by one taken
    # from its bytes: the next can then begin before this one is read. Out of line, so that a str
    # of ASCII pays nothing for it
    n = 0
    while n < left:
        c = _rt.byte_at(p, n)
        if c < 128:
            if c < 32 or c == 127 or c == q or c == 92:
                break
            n += 1
        elif c >= 0xC2 and c < 0xE0 and left - n > 1 and _rt.byte_at(p, n + 1) & 0xC0 == 0x80:
            if pys_rt_printable((c & 0x1F) << 6 | (_rt.byte_at(p, n + 1) & 0x3F)) == 0:
                break
            n += 2
        elif c >= 0xE0 and c < 0xF0 and left - n > 2 and _rt.byte_at(p, n + 1) & 0xC0 == 0x80 and _rt.byte_at(p, n + 2) & 0xC0 == 0x80 and ((c & 0x0F) << 12 | (_rt.byte_at(p, n + 1) & 0x3F) << 6 | (_rt.byte_at(p, n + 2) & 0x3F)) >= 0x800:
            if pys_rt_printable((c & 0x0F) << 12 | (_rt.byte_at(p, n + 1) & 0x3F) << 6 | (_rt.byte_at(p, n + 2) & 0x3F)) == 0:
                break
            n += 3
        else:
            k = u8_point(_rt.offset(p, n), left - n)
            if pys_rt_printable(k >> 3) == 0:
                break
            n += k & 7
    return n


@_rt.unchecked
def pys_rt_repr_str(b: _rt.Ptr, s: str) -> None:
    # repr(s) onto b, as CPython's unicode_repr writes it: runs of printable ASCII, and of other
    # printable characters, as they are; the others escaped
    n = len(s)
    p = str_bytes(s)
    q = 34 if _rt.find_byte(s, 39, 0, n) >= 0 and _rt.find_byte(s, 34, 0, n) < 0 else 39
    t = _rt.words(2)
    put_char(b, q)
    i = 0
    while i < n:
        k = 0
        while i + k < n:
            c = _rt.byte_at(p, i + k)
            if c < 32 or c > 126 or c == q or c == 92:
                break
            k += 1
        if k == 0 and _rt.byte_at(p, i) > 127:
            k = printable_run(_rt.offset(p, i), n - i, q)
        if k != 0:
            pys_rt_put(b, _rt.offset(p, i), k)
        else:
            r = char_repr(t, _rt.offset(p, i), n - i, q)
            pys_rt_put(b, t, r & 255)
            k = r >> 8
        i += k
    put_char(b, q)


@_rt.unchecked
def repr_bytes(b: _rt.Ptr, s: str) -> None:
    # a bytes's repr(), as CPython's PyBytes_Repr writes it: b and the quotes; \t, \n, \r, \xhh
    # below 32 and from 127 on, \\ and the quote
    n = len(s)
    p = str_bytes(s)
    q = 34 if _rt.find_byte(s, 39, 0, n) >= 0 and _rt.find_byte(s, 34, 0, n) < 0 else 39
    t = _rt.words(1)
    put_char(b, ord("b"))
    put_char(b, q)
    i = 0
    while i < n:
        k = 0
        while i + k < n:
            c = _rt.byte_at(p, i + k)
            if c < 32 or c > 126 or c == q or c == 92:
                break
            k += 1
        if k != 0:
            pys_rt_put(b, _rt.offset(p, i), k)
            i += k
            continue
        c = _rt.byte_at(p, i)
        _rt.put_byte(t, 0, 92)
        if c == q or c == 92 or c == 9 or c == 10 or c == 13:
            _rt.put_byte(t, 1, ord("t") if c == 9 else ord("n") if c == 10 else ord("r") if c == 13 else c)
            pys_rt_put(b, t, 2)
        else:
            _rt.put_byte(t, 1, ord("x"))
            _rt.put_byte(t, 2, hex_digit(c >> 4))
            _rt.put_byte(t, 3, hex_digit(c & 15))
            pys_rt_put(b, t, 4)
        i += 1
    put_char(b, q)


@_rt.unchecked
def repr_walk(b: _rt.Ptr, v: int, d: _rt.Ptr, depth: int) -> _rt.Ptr:
    # repr(v) onto b by descriptor d: the bytes past d's part (runtime.c's repr_depth). depth
    # counts the recursive alias edges (R) followed: a recursive value can nest without bound, so
    # following more than 512 raises RecursionError, as CPython's repr does for deep nesting;
    # other reprs, a class's own __repr__ among them, are limited only by the native stack
    c = _rt.byte_at(d, 0)
    e = _rt.offset(d, 1)
    if c == ord("i"):
        put_int(b, v)
        return e
    if c == ord("s"):
        if v != 0:
            pys_rt_repr_str(b, _rt.as_str(_rt.ptr(v)))
        else:
            put_text(b, "None")  # (None in a looked-up key: see runtime.c's hval)
        return e
    if c == ord("f"):
        put_text(b, pys_str_float(_rt.bits_float(v)))
        return e
    if c == ord("b"):
        put_text(b, "True" if v != 0 else "False")
        return e
    if c == ord("R"):
        if depth >= 512:
            pys_rt_rec_deep(0)
        repr_walk(b, v, recdesc(d), depth + 1)
        return pys_rt_skip(d)
    if c == ord("U"):
        end = pys_rt_skip(d)
        if v == 0:
            put_text(b, "None")  # (None, which a union of classes may hold: a KeyError's key, #1452)
            return end
        box = _rt.ptr(v)
        repr_walk(b, _rt.word(box, 1), pys_rt_utype(_rt.word(box, 0), d), depth)
        return end
    if c == ord("A"):
        x = _rt.ptr(v)
        repr_walk(b, _rt.get(x, "Dyn.v"), desc_of(_rt.getp(_rt.getp(x, "Dyn.t"), "DynType.desc")), depth)
        return e
    if c == ord("G"):
        put_text(b, "<generator object>")
        return e
    if c == ord("Q"):
        put_text(b, "<iterator object>")
        return e
    if c == ord("Z"):
        put_text(b, "<function>")  # (a dynamic value's function: by identity, unnamed)
        return e
    if c == ord("Y"):
        # a class value: its reflection record's name, qualified name and module
        r = _rt.ptr(v)
        put_text(b, "<class '")
        if pys_str_eq(_rt.as_str(_rt.getp(r, "ReflRec.mod")), "builtins") == 0:
            put_text(b, _rt.as_str(_rt.getp(r, "ReflRec.mod")))
            put_char(b, ord("."))
        put_text(b, _rt.as_str(_rt.getp(r, "ReflRec.qual")))
        put_text(b, "'>")
        return e
    if c == ord("J"):
        # a promoting int's two words
        pys_rt_opt_in()
        m = jbig_hi(v)
        if not _rt.null(m):
            put_digits(b, m)
        else:
            put_int(b, jbig_lo(v))
        return e
    if c == ord("j"):
        # a dynamic wide int's immutable Mpz
        pys_rt_opt_in()
        put_digits(b, _rt.ptr(v))
        return e
    if c == ord("y"):
        if v != 0:
            repr_bytes(b, _rt.as_str(_rt.ptr(v)))
        else:
            put_text(b, "None")
        return e
    if c == ord("L"):
        # a list or dict being printed already (through an object) is [...] or {...}
        l = _rt.ptr(v)
        if pys_repr_enter(l) == 0:
            put_text(b, "[...]")
            return pys_rt_skip(e)
        put_char(b, ord("["))
        i = 0
        while i < _rt.get(l, "List.len"):
            if i != 0:
                put_text(b, ", ")
            m = pys_rt_lbig(l, i)  # (an int past 64 bits)
            if not _rt.null(m):
                put_digits(b, m)
            else:
                repr_walk(b, _rt.word(_rt.getp(l, "List.a"), i), e, depth)
            i += 1
        put_char(b, ord("]"))
        pys_repr_leave(l)
        return pys_rt_skip(e)
    if c == ord("D"):
        m = _rt.ptr(v)
        dv = pys_rt_skip(e)
        if pys_repr_enter(m) == 0:
            put_text(b, "{...}")
            return pys_rt_skip(dv)
        put_char(b, ord("{"))
        j = 0
        k = 0
        while j < _rt.get(m, "Dict.n"):
            if dict_live(m, j):
                if k != 0:
                    put_text(b, ", ")
                k += 1
                # (a key's __repr__ may empty the dict: all four are read first)
                key = _rt.word(_rt.getp(m, "Dict.keys"), j)
                val = _rt.word(_rt.getp(m, "Dict.vals"), j)
                big = pys_rt_dbig(m, j)
                kbm = dict_key_big(m, j)
                if not _rt.null(kbm):
                    put_digits(b, kbm)
                else:
                    repr_walk(b, key, e, depth)
                put_text(b, ": ")
                if not _rt.null(big):
                    put_digits(b, big)
                else:
                    repr_walk(b, val, dv, depth)
            j += 1
        put_char(b, ord("}"))
        pys_repr_leave(m)
        return pys_rt_skip(dv)
    if c == ord("S") or c == ord("F"):
        # set() or {1, 2}; frozenset() or frozenset({1, 2})
        s = _rt.ptr(v)
        fz = c == ord("F")
        if _rt.get(s, "Set.len") == 0:
            put_text(b, "frozenset()" if fz else "set()")
            return pys_rt_skip(e)
        # (one being printed already, through an element's __repr__, is set(...), as CPython's
        # set_repr prints it: #1586)
        if pys_repr_enter(s) == 0:
            put_text(b, "frozenset(...)" if fz else "set(...)")
            return pys_rt_skip(e)
        put_text(b, "frozenset({" if fz else "{")
        i = 0
        k = 0
        while i <= _rt.get(s, "Set.mask"):
            if _rt.word(_rt.getp(s, "Set.hs"), i) != -1:
                if k != 0:
                    put_text(b, ", ")
                k += 1
                m = pys_rt_sbig(s, i)  # (an int past 64 bits)
                if not _rt.null(m):
                    put_digits(b, m)
                else:
                    repr_walk(b, _rt.word(_rt.getp(s, "Set.keys"), i), e, depth)
            i += 1
        put_text(b, "})" if fz else "}")
        pys_repr_leave(s)
        return pys_rt_skip(e)
    if c == ord("T"):
        if v == 0:
            put_text(b, "None")
            return pys_rt_skip(d)
        n = _rt.byte_at(e, 0) - 48
        e = _rt.offset(e, 1)
        t = _rt.ptr(v)
        w = _rt.words(2)
        put_char(b, ord("("))
        i = 0
        while i < n:
            if i != 0:
                put_text(b, ", ")
            e = repr_walk(b, tuple_item(t, n, i, e, w), e, depth)
            i += 1
        put_text(b, ",)" if n == 1 else ")")
        return e
    if c == ord("V"):
        if v == 0:
            put_text(b, "None")
            return pys_rt_skip(e)
        t = _rt.ptr(v)
        if pys_repr_enter(t) == 0:
            put_text(b, "(...)")
            return pys_rt_skip(e)
        put_char(b, ord("("))
        i = 0
        while i < _rt.get(t, "VTuple.len"):
            if i != 0:
                put_text(b, ", ")
            repr_walk(b, _rt.word(vtuple_items(t), i), e, depth)
            i += 1
        put_text(b, ",)" if _rt.get(t, "VTuple.len") == 1 else ")")
        pys_repr_leave(t)
        return pys_rt_skip(e)
    if c == ord("O") or c == ord("P") or c == ord("H"):
        put_text(b, pys_obj_repr(pys_rt_ocls(e), v, 0))
        return pys_rt_skip(d)
    if c == ord("?"):
        if v != 0:
            return repr_walk(b, unbox(v, e), e, depth)
        put_text(b, "None")
        return pys_rt_skip(e)
    if c == ord("E"):
        put_text(b, pys_exc_repr(_rt.ptr(v)))
        return e
    if c == ord("C"):
        put_text(b, pys_exc_type(_rt.ptr(v)))  # (an exception class: its class object)
        return e
    return e


@_rt.unchecked
def pys_rt_repr_to(b: _rt.Ptr, v: int, d: _rt.Ptr) -> None:
    # repr(v) of descriptor d (its bytes) onto b, for runtime.c's messages
    repr_walk(b, v, d, 0)


@_rt.unchecked
def pys_repr(v: int, d: _rt.Ptr) -> str:
    b = _rt.local("Buf")
    buf_open(b)
    repr_walk(b, v, desc_of(d), 0)
    return buf_done(b)


# ---- equality


@_rt.unchecked
def list_same_item(a: _rt.Ptr, i: int, b: _rt.Ptr, j: int) -> bool:
    # are a[i] and b[j] one object, by the lists' identity companions
    x = _rt.getp(a, "List.ids")
    y = _rt.getp(b, "List.ids")
    if _rt.null(x) or _rt.null(y) or pys_rt_opt_in() == 0:
        return False
    if _rt.addr(a) == _rt.addr(b) and i == j:
        return True
    k = _rt.word(x, i + 1)
    return k != 0 and k == _rt.word(y, j + 1)


@_rt.unchecked
def list_item_eq(x: _rt.Ptr, i: int, y: _rt.Ptr, j: int, d: _rt.Ptr) -> bool:
    # x[i] == y[j] of lists of one type: ints past 64 bits equal their values only
    m = pys_rt_lbig(x, i)
    n = pys_rt_lbig(y, j)
    if not _rt.null(m) or not _rt.null(n):
        return not _rt.null(m) and not _rt.null(n) and pys_mpz_cmp(m, n) == 0
    return list_same_item(x, i, y, j) or eqitem(_rt.word(_rt.getp(x, "List.a"), i), _rt.word(_rt.getp(y, "List.a"), j), d)


@_rt.unchecked
def pys_rt_list_item_eq(l: _rt.Ptr, i: int, v: int, d: str) -> int:
    # l[i] == v of the list searches (lists.py's), where an item's __eq__ may run
    if not _rt.null(pys_rt_lbig(l, i)):
        return 0
    return 1 if eqitem(_rt.word(_rt.getp(l, "List.a"), i), v, str_bytes(d)) else 0


@_rt.unchecked
def eqitem(a: int, b: int, d: _rt.Ptr) -> bool:
    # Container items use identity before equality (PyObject_RichCompareBool). This stays apart
    # from direct comparison: equal unboxed float bits need not compare equal, and an optional
    # scalar's box gives that scalar no Python object identity
    d = recdesc(d)
    c = _rt.byte_at(d, 0)
    if c == ord("i") or c == ord("b"):
        return a == b  # (eqv's answer for an int or a bool, and for a str below, without its call)
    if c == ord("s"):
        return str_item_eq(a, b)
    if c == ord("?"):
        c = _rt.byte_at(d, 1)
    if c == ord("U"):
        return eqpair_walk(a, b, d, d, 0)
    if c == ord("A"):
        return pys_rt_dyn_eqitem(_rt.ptr(a), _rt.ptr(b)) != 0
    if a == b and (c == ord("L") or c == ord("D") or c == ord("T") or c == ord("V") or c == ord("S") or c == ord("F")):
        return True
    return eqv(a, b, d)


@_rt.unchecked
def eqv(a: int, b: int, d: _rt.Ptr) -> bool:
    # a == b of one descriptor d
    d = recdesc(d)
    pys_rt_eq_probe()
    c = _rt.byte_at(d, 0)
    if c == ord("s"):
        if a != 0 and b != 0:
            return pys_str_eq(_rt.as_str(_rt.ptr(a)), _rt.as_str(_rt.ptr(b))) != 0
        return a == b  # (None in a looked-up key: see runtime.c's hval)
    if c == ord("f"):
        return _rt.bits_float(a) == _rt.bits_float(b)
    if c == ord("U"):
        return eqpair_walk(a, b, d, d, 0)
    if c == ord("A"):
        return pys_dyn_eq(_rt.ptr(a), _rt.ptr(b)) != 0
    if c == ord("J"):
        pys_rt_opt_in()
        return pys_big_cmp(jbig_lo(a), jbig_hi(a), jbig_lo(b), jbig_hi(b)) == 0
    if c == ord("L"):
        # an __eq__ may change either list: as CPython's list_richcompare, both lengths are read
        # again at every step, and once a list has no item left they are compared
        x = _rt.ptr(a)
        y = _rt.ptr(b)
        if _rt.get(x, "List.len") != _rt.get(y, "List.len"):
            return False
        e = _rt.offset(d, 1)
        i = 0
        while i < _rt.get(x, "List.len") and i < _rt.get(y, "List.len") and list_item_eq(x, i, y, i, e):
            i += 1
        return (i >= _rt.get(x, "List.len") or i >= _rt.get(y, "List.len")) and _rt.get(x, "List.len") == _rt.get(y, "List.len")
    if c == ord("D"):
        return dict_eq(_rt.ptr(a), _rt.ptr(b), _rt.offset(d, 1))
    if c == ord("T"):
        if a == 0 or b == 0:
            return a == b
        x = _rt.ptr(a)
        y = _rt.ptr(b)
        n = _rt.byte_at(d, 1) - 48
        e = _rt.offset(d, 2)
        wx = _rt.words(2)
        wy = _rt.words(2)
        i = 0
        while i < n:
            p = _rt.word(x, i)
            q = _rt.word(y, i)
            if _rt.byte_at(e, 0) == ord("J") and p != -9223372036854775807 - 1 and q != -9223372036854775807 - 1:
                # (promoting ints that fit: their slots)
                if p != q:
                    return False
            elif not eqitem(tuple_item(x, n, i, e, wx), tuple_item(y, n, i, e, wy), e):
                return False
            e = desc_next(e)
            i += 1
        return True
    if c == ord("V"):
        # as CPython's tuplerichcompare: the items both have, then the lengths (lists test lengths
        # first; tuples do not, so an object item's __eq__ runs anyway)
        if a == b:
            return True
        if a == 0 or b == 0:
            return False
        x = _rt.ptr(a)
        y = _rt.ptr(b)
        e = _rt.offset(d, 1)
        i = 0
        while i < _rt.get(x, "VTuple.len") and i < _rt.get(y, "VTuple.len") and (vtuple_same(x, y, i) or eqitem(_rt.word(vtuple_items(x), i), _rt.word(vtuple_items(y), i), e)):
            i += 1
        return i >= _rt.get(x, "VTuple.len") and i >= _rt.get(y, "VTuple.len")
    if c == ord("S") or c == ord("F"):
        return pys_set_cmp(_rt.ptr(a), _rt.ptr(b), 4) != 0  # (a set equals a frozenset of its elements)
    if c == ord("O") or c == ord("H"):
        return a == b or pys_obj_eq(pys_rt_ocls(_rt.offset(d, 1)), a, b) != 0  # (identity first, as CPython)
    if c == ord("?"):
        if a != 0 and b != 0:
            return eqv(unbox(a, _rt.offset(d, 1)), unbox(b, _rt.offset(d, 1)), _rt.offset(d, 1))
        return a == b  # (None equals only None)
    if c == ord("E"):
        return _rt.addr(pys_exc_id(_rt.ptr(a))) == _rt.addr(pys_exc_id(_rt.ptr(b)))
    return a == b


@_rt.unchecked
def dict_eq(x: _rt.Ptr, y: _rt.Ptr, d: _rt.Ptr) -> bool:
    # x == y of dicts of key descriptor d, as CPython's dict_equal: each of x's keys looked up in
    # y, with the hash x keeps where y's keys are of the same kind
    dv = pys_rt_skip(d)
    kx = _rt.get(x, "Dict.kind")
    ky = _rt.get(y, "Dict.kind")
    same = kx == ky or (kx > 1 and ky > 1 and desc_text_eq(kind_desc(kx), kind_desc(ky)))
    if _rt.get(x, "Dict.len") != _rt.get(y, "Dict.len"):
        return False
    e = 0
    while e < _rt.get(x, "Dict.n"):
        if dict_live(x, e):
            val = _rt.word(_rt.getp(x, "Dict.vals"), e)
            xb = pys_rt_dbig(x, e)
            xk = dict_key_big(x, e)  # (a key past 64 bits)
            h = _rt.word(_rt.getp(x, "Dict.hs"), e)
            f = -1
            # (a key's __eq__ may empty x: what the lookup needs is read first)
            if not _rt.null(xk):
                f = pys_rt_dbfind(y, xk, h)
                f = _rt.i32_at(_rt.getp(y, "Dict.idx"), f) - 1 if f >= 0 else -1
            elif same:
                f = pys_rt_dfind(y, _rt.word(_rt.getp(x, "Dict.keys"), e), h)
                f = _rt.i32_at(_rt.getp(y, "Dict.idx"), f) - 1 if f >= 0 else -1
            else:
                f = dict_entry(y, _rt.word(_rt.getp(x, "Dict.keys"), e))
            if f < 0:
                return False
            yb = pys_rt_dbig(y, f)  # (values past 64 bits: equal to their values only)
            if not _rt.null(xb) or not _rt.null(yb):
                if _rt.null(xb) or _rt.null(yb) or pys_mpz_cmp(xb, yb) != 0:
                    return False
            elif not eqitem(val, _rt.word(_rt.getp(y, "Dict.vals"), f), dv):
                return False
        e += 1
    return True


@_rt.unchecked
def eq_resolve(v: int, d: _rt.Ptr, out: _rt.Ptr) -> _rt.Ptr:
    # Each operand has its own layout: an optional number is a one-slot box, a union is a
    # tag/payload box, and a concrete container is its original pointer. The descriptor v has
    # past them ("n" for None); its value in out's word 0, and in word 1 whether a recursive
    # alias's edge (R) led here
    edge = 0
    while True:
        c = _rt.byte_at(d, 0)
        if c == ord("R"):
            d = recdesc(d)
            edge = 1
        elif c == ord("?"):
            if v == 0:
                d = str_bytes("n")
                break
            d = _rt.offset(d, 1)
            v = unbox(v, d)
        elif c == ord("U"):
            if v == 0:
                d = str_bytes("n")  # (None: a union key's, #1452)
                break
            box = _rt.ptr(v)
            d = pys_rt_utype(_rt.word(box, 0), d)
            v = _rt.word(box, 1)
        else:
            break
    _rt.put(out, 0, v)
    _rt.put(out, 1, edge)
    return d


@_rt.unchecked
def pys_rt_eqresolve(v: int, d: _rt.Ptr, out: _rt.Ptr) -> _rt.Ptr:
    return eq_resolve(v, d, out)


@_rt.unchecked
def big_eq(m: _rt.Ptr, b: int, y: _rt.Ptr) -> bool:
    # the int m past 64 bits == value b of descriptor y (no 64-bit int or bool equals it)
    r = _rt.words(2)
    e = eq_resolve(b, y, r)
    return _rt.byte_at(e, 0) == ord("f") and pys_rt_mpz_cmp_float(m, _rt.bits_float(_rt.word(r, 0))) == 0


@_rt.unchecked
def eqpair_walk(a: int, b: int, x: _rt.Ptr, y: _rt.Ptr, depth: int) -> bool:
    # a == b of descriptors x and y (runtime.c's eqpair_depth). Only closed builtin value trees
    # reach this path (the compiler rejects user callbacks), and objects that compare by identity
    # (P: a union key's member). b is never decoded with x: equal Python types may have different
    # native element layouts, nested unions and boxed optionals among them
    pys_rt_eq_probe()
    r = _rt.words(2)
    x = eq_resolve(a, x, r)
    a = _rt.word(r, 0)
    edge = _rt.word(r, 1)
    y = eq_resolve(b, y, r)
    b = _rt.word(r, 0)
    edge = edge | _rt.word(r, 1)
    cx = _rt.byte_at(x, 0)
    cy = _rt.byte_at(y, 0)
    tx = cx == ord("T") or cx == ord("V")
    ty = cy == ord("T") or cy == ord("V")
    # The original container's identity survives separate union boxes. Besides matching Python,
    # this keeps a shared DAG from expanding into its logical tree. Scalar boxes deliberately
    # confer no numeric identity (notably for NaNs)
    if a == b and (cx == cy or (tx and ty)) and (cx == ord("L") or cx == ord("D") or tx):
        return True
    # Recursive values can form cycles after parsing. Distinct cycles raise, as Python does,
    # while shared descendants keep the identity shortcut above. depth counts the recursive
    # alias edges followed, as repr_walk's does, and is checked before any leaf is compared, so
    # the 513th edge raises whatever it leads to
    if edge != 0:
        if depth >= 512:
            pys_rt_rec_deep(1)
        depth += 1
    if cx == ord("n") or cy == ord("n"):
        return cx == cy
    if (cx == ord("J") or cy == ord("J")) and pys_rt_opt_in() != 0:
        # a promoting int and a number, exactly; another type equals it never
        jv = a if cx == ord("J") else b
        ov = b if cx == ord("J") else a
        ce = cy if cx == ord("J") else cx
        hi = jbig_hi(jv)
        lo = jbig_lo(jv)
        if ce == ord("J"):
            return pys_big_cmp(lo, hi, jbig_lo(ov), jbig_hi(ov)) == 0
        if ce == ord("f"):
            # (allocating nothing)
            return (pys_rt_mpz_cmp_float(hi, _rt.bits_float(ov)) if not _rt.null(hi) else pys_cmp_if(lo, _rt.bits_float(ov))) == 0
        return (ce == ord("i") or ce == ord("b")) and _rt.null(hi) and lo == ov
    nx = cx == ord("i") or cx == ord("b")
    ny = cy == ord("i") or cy == ord("b")
    if nx and ny:
        return a == b
    if nx and cy == ord("f"):
        return pys_cmp_if(a, _rt.bits_float(b)) == 0
    if cx == ord("f") and ny:
        return pys_cmp_if(b, _rt.bits_float(a)) == 0
    if cx != cy and not (tx and ty):
        return False
    if cx == ord("f"):
        return _rt.bits_float(a) == _rt.bits_float(b)
    if cx == ord("s"):
        if a != 0 and b != 0:
            return pys_str_eq(_rt.as_str(_rt.ptr(a)), _rt.as_str(_rt.ptr(b))) != 0
        return a == b
    if cx == ord("P"):
        return a == b  # (objects of union keys' classes, which compare by identity: #1452)
    if cx == ord("L"):
        p = _rt.ptr(a)
        q = _rt.ptr(b)
        if _rt.get(p, "List.len") != _rt.get(q, "List.len"):
            return False
        ex = _rt.offset(x, 1)
        ey = _rt.offset(y, 1)
        i = 0
        while i < _rt.get(p, "List.len"):
            m = pys_rt_lbig(p, i)  # (ints past 64 bits)
            n = pys_rt_lbig(q, i)
            if not _rt.null(m) and not _rt.null(n):
                if pys_mpz_cmp(m, n) != 0:
                    return False
            elif not _rt.null(m):
                if not big_eq(m, _rt.word(_rt.getp(q, "List.a"), i), ey):
                    return False
            elif not _rt.null(n):
                if not big_eq(n, _rt.word(_rt.getp(p, "List.a"), i), ex):
                    return False
            elif not list_same_item(p, i, q, i) and not eqpair_walk(_rt.word(_rt.getp(p, "List.a"), i), _rt.word(_rt.getp(q, "List.a"), i), ex, ey, depth):
                return False
            i += 1
        return True
    if cx == ord("D"):
        return dict_eqpair(_rt.ptr(a), _rt.ptr(b), _rt.offset(x, 1), _rt.offset(y, 1), depth)
    if tx:
        if a == 0 or b == 0:
            return a == b
        xt = cx == ord("T")
        yt = cy == ord("T")
        cnt = _rt.byte_at(x, 1) - 48 if xt else _rt.get(_rt.ptr(a), "VTuple.len")
        if cnt != (_rt.byte_at(y, 1) - 48 if yt else _rt.get(_rt.ptr(b), "VTuple.len")):
            return False
        p = _rt.ptr(a) if xt else vtuple_items(_rt.ptr(a))
        q = _rt.ptr(b) if yt else vtuple_items(_rt.ptr(b))
        ex = _rt.offset(x, 2 if xt else 1)
        ey = _rt.offset(y, 2 if yt else 1)
        wx = _rt.words(2)
        wy = _rt.words(2)
        i = 0
        while i < cnt:
            if not (not xt and not yt and vtuple_same(_rt.ptr(a), _rt.ptr(b), i)):
                if not eqpair_walk(tuple_item(p, cnt, i, ex, wx) if xt else _rt.word(p, i), tuple_item(q, cnt, i, ey, wy) if yt else _rt.word(q, i), ex, ey, depth):
                    return False
            if xt:
                ex = desc_next(ex)
            if yt:
                ey = desc_next(ey)
            i += 1
        return True
    return False  # (not reached: the compiler permits only the builtin value descriptors above)


@_rt.unchecked
def dict_eqpair(p: _rt.Ptr, q: _rt.Ptr, kx: _rt.Ptr, ky: _rt.Ptr, depth: int) -> bool:
    # p == q of dicts whose key descriptors are kx and ky, which may differ: a key is looked up
    # where both describe one type, or ints and bools; else found by comparing it with each
    vx = pys_rt_skip(kx)
    vy = pys_rt_skip(ky)
    if _rt.get(p, "Dict.len") != _rt.get(q, "Dict.len"):
        return False
    lookup = same_desc(kx, ky) or ((_rt.byte_at(kx, 0) == ord("i") or _rt.byte_at(kx, 0) == ord("b")) and (_rt.byte_at(ky, 0) == ord("i") or _rt.byte_at(ky, 0) == ord("b")))
    i = 0
    while i < _rt.get(p, "Dict.n"):
        if dict_live(p, i):
            j = -1
            pk = dict_key_big(p, i)
            if not _rt.null(pk):
                # (a key past 64 bits equals such a key only)
                j = pys_rt_dbfind(q, pk, _rt.word(_rt.getp(p, "Dict.hs"), i))
                j = _rt.i32_at(_rt.getp(q, "Dict.idx"), j) - 1 if j >= 0 else -1
            elif lookup:
                j = dict_entry(q, _rt.word(_rt.getp(p, "Dict.keys"), i))
            else:
                k = 0
                while k < _rt.get(q, "Dict.n"):
                    if dict_live(q, k) and _rt.null(dict_key_big(q, k)) and eqpair_walk(_rt.word(_rt.getp(p, "Dict.keys"), i), _rt.word(_rt.getp(q, "Dict.keys"), k), kx, ky, depth):
                        j = k
                        break
                    k += 1
            if j < 0:
                return False
            m = pys_rt_dbig(p, i)  # (values past 64 bits)
            n = pys_rt_dbig(q, j)
            if not _rt.null(m) and not _rt.null(n):
                if pys_mpz_cmp(m, n) != 0:
                    return False
            elif not _rt.null(m):
                if not big_eq(m, _rt.word(_rt.getp(q, "Dict.vals"), j), vy):
                    return False
            elif not _rt.null(n):
                if not big_eq(n, _rt.word(_rt.getp(p, "Dict.vals"), i), vx):
                    return False
            elif not eqpair_walk(_rt.word(_rt.getp(p, "Dict.vals"), i), _rt.word(_rt.getp(q, "Dict.vals"), j), vx, vy, depth):
                return False
        i += 1
    return True


@_rt.unchecked
def pys_eq(a: int, b: int, d: _rt.Ptr) -> int:
    # a == b of descriptor d. Of two strs ("s", which the compiler passes for every str == str
    # and str != str): eqv's answer, without its walk
    p = desc_of(d)
    if _rt.byte_at(p, 0) == ord("s"):
        if a != 0 and b != 0:
            return pys_str_eq(_rt.as_str(_rt.ptr(a)), _rt.as_str(_rt.ptr(b)))
        return 1 if a == b else 0
    return 1 if eqv(a, b, p) else 0


@_rt.unchecked
def pys_eq_pair(a: int, b: int, x: _rt.Ptr, y: _rt.Ptr) -> int:
    return 1 if eqpair_walk(a, b, desc_of(x), desc_of(y), 0) else 0


@_rt.unchecked
def pys_rt_eqv(a: int, b: int, d: _rt.Ptr) -> int:
    # for runtime.c's walks, which have a descriptor's bytes (d): eqv, eqitem, eqpair and big_eq
    return 1 if eqv(a, b, d) else 0


@_rt.unchecked
def pys_rt_eqitem(a: int, b: int, d: _rt.Ptr) -> int:
    return 1 if eqitem(a, b, d) else 0


@_rt.unchecked
def pys_rt_eqpair(a: int, b: int, x: _rt.Ptr, y: _rt.Ptr) -> int:
    return 1 if eqpair_walk(a, b, x, y, 0) else 0


@_rt.unchecked
def pys_rt_big_eq(m: _rt.Ptr, b: int, y: _rt.Ptr) -> int:
    return 1 if big_eq(m, b, y) else 0


# ---- ordering


@_rt.unchecked
def cmpop(c: int, op: int) -> bool:
    # c, a comparison's -1, 0 or 1, as op 0..3, < <= > >=
    return c < 0 if op == 0 else c <= 0 if op == 1 else c > 0 if op == 2 else c >= 0


def sign(a: int, b: int) -> int:
    return 1 if a > b else -1 if a < b else 0


def float_op(x: float, y: float, op: int) -> bool:
    return x < y if op == 0 else x <= y if op == 1 else x > y if op == 2 else x >= y


@_rt.unchecked
def type_letter(v: int, d: _rt.Ptr) -> int:
    # the descriptor letter of v's type (a union's: its member's), for an ordering's TypeError
    if _rt.byte_at(d, 0) != ord("U"):
        return _rt.byte_at(d, 0)
    r = _rt.words(2)
    return _rt.byte_at(eq_resolve(v, d, r), 0)


@_rt.unchecked
def list_order(x: _rt.Ptr, y: _rt.Ptr, e: _rt.Ptr, op: int) -> bool:
    # x OP y of lists of item descriptor e: the first pair of items that are not equal decides
    i = 0
    while i < _rt.get(x, "List.len") and i < _rt.get(y, "List.len") and list_item_eq(x, i, y, i, e):
        i += 1
    if i < _rt.get(x, "List.len") and i < _rt.get(y, "List.len"):
        mx = pys_rt_lbig(x, i)
        my = pys_rt_lbig(y, i)
        if not _rt.null(mx) or not _rt.null(my):
            # (an int past 64 bits)
            return cmpop(pys_big_cmp(0 if not _rt.null(mx) else _rt.word(_rt.getp(x, "List.a"), i), mx, 0 if not _rt.null(my) else _rt.word(_rt.getp(y, "List.a"), i), my), op)
        return opv(_rt.word(_rt.getp(x, "List.a"), i), _rt.word(_rt.getp(y, "List.a"), i), e, op)
    return cmpop(sign(_rt.get(x, "List.len"), _rt.get(y, "List.len")), op)


@_rt.unchecked
def opv(a: int, b: int, d: _rt.Ptr, op: int) -> bool:
    # a OP b of descriptor d, op 0..3 for < <= > >=, as CPython compares: sequences find the
    # first pair of items that are not equal (identity, then ==) and apply OP to that pair only,
    # else compare lengths; objects go through the program's rich comparison (reflection,
    # TypeError)
    c = _rt.byte_at(d, 0)
    e = _rt.offset(d, 1)
    if c == ord("f"):
        return float_op(_rt.bits_float(a), _rt.bits_float(b), op)
    if c == ord("s"):
        return cmpop(pys_str_cmp(_rt.as_str(_rt.ptr(a)), _rt.as_str(_rt.ptr(b))), op)
    if c == ord("L"):
        return list_order(_rt.ptr(a), _rt.ptr(b), e, op)
    if c == ord("J"):
        pys_rt_opt_in()
        return cmpop(pys_big_cmp(jbig_lo(a), jbig_hi(a), jbig_lo(b), jbig_hi(b)), op)
    if c == ord("T"):
        x = _rt.ptr(a)
        y = _rt.ptr(b)
        n = _rt.byte_at(e, 0) - 48
        e = _rt.offset(e, 1)
        wx = _rt.words(2)
        wy = _rt.words(2)
        i = 0
        while i < n:
            if _rt.byte_at(e, 0) == ord("J") and _rt.word(x, i) != -9223372036854775807 - 1 and _rt.word(y, i) != -9223372036854775807 - 1:
                # (as eqv's)
                if _rt.word(x, i) != _rt.word(y, i):
                    return cmpop(sign(_rt.word(x, i), _rt.word(y, i)), op)
            else:
                p = tuple_item(x, n, i, e, wx)
                q = tuple_item(y, n, i, e, wy)
                if not eqitem(p, q, e):
                    return opv(p, q, e, op)
            e = desc_next(e)
            i += 1
        return cmpop(0, op)
    if c == ord("V"):
        if a == b:
            return cmpop(0, op)
        x = _rt.ptr(a)
        y = _rt.ptr(b)
        i = 0
        while i < _rt.get(x, "VTuple.len") and i < _rt.get(y, "VTuple.len") and (vtuple_same(x, y, i) or eqitem(_rt.word(vtuple_items(x), i), _rt.word(vtuple_items(y), i), e)):
            i += 1
        if i < _rt.get(x, "VTuple.len") and i < _rt.get(y, "VTuple.len"):
            return opv(_rt.word(vtuple_items(x), i), _rt.word(vtuple_items(y), i), e, op)
        return cmpop(sign(_rt.get(x, "VTuple.len"), _rt.get(y, "VTuple.len")), op)
    if c == ord("S") or c == ord("F"):
        return pys_set_cmp(_rt.ptr(a), _rt.ptr(b), op) != 0  # (subsets)
    if c == ord("O"):
        return pys_obj_cmp(pys_rt_ocls(e), op, a, b) != 0
    if c == ord("A"):
        return pys_dyn_cmp(_rt.ptr(a), _rt.ptr(b), op) != 0
    if c == ord("K"):
        # key='s records {key, value}: their keys
        return opv(_rt.word(_rt.ptr(a), 0), _rt.word(_rt.ptr(b), 0), e, op)
    if c == ord("U"):
        # numbers of a union (the compiler orders no other): an int and a float exactly, as CPython
        r = _rt.words(2)
        fx = _rt.byte_at(eq_resolve(a, d, r), 0) == ord("f")
        va = _rt.word(r, 0)
        fy = _rt.byte_at(eq_resolve(b, d, r), 0) == ord("f")
        vb = _rt.word(r, 0)
        if not fx and not fy:
            return cmpop(sign(va, vb), op)
        if fx and fy:
            return float_op(_rt.bits_float(va), _rt.bits_float(vb), op)
        k = pys_cmp_if(va, _rt.bits_float(vb)) if not fx else pys_cmp_if(vb, _rt.bits_float(va))
        return k != 2 and cmpop(k if not fx else 0 - k, op)  # (2: a NaN, for which no ordering holds)
    if c == ord("D"):
        pys_rt_order_error(op, c, c, _rt.nil(), _rt.nil())
    if c == ord("?"):
        if a != 0 and b != 0:
            return opv(unbox(a, e), unbox(b, e), e, op)
        pys_rt_order_error(op, type_letter(a, e) if a != 0 else ord("n"), type_letter(b, e) if b != 0 else ord("n"), _rt.nil(), _rt.nil())
    if c == ord("C") or c == ord("Y"):
        pys_rt_order_error(op, ord("C"), ord("C"), _rt.nil(), _rt.nil())
    if c == ord("E"):
        pys_rt_order_error(op, c, c, _rt.ptr(a), _rt.ptr(b))
    return cmpop(sign(a, b), op)


@_rt.unchecked
def pys_cmpop(a: int, b: int, d: _rt.Ptr, op: int) -> int:
    return 1 if opv(a, b, desc_of(d), op) else 0


@_rt.unchecked
def pys_rt_opv(a: int, b: int, d: _rt.Ptr, op: int) -> int:
    return 1 if opv(a, b, d, op) else 0


# ---------- floats and ints: division, conversion, rounding, comparison ----------
# What Python defines where C does not: a zero divisor, a NaN or an infinity that has no int,
# and a float past 64 bits. The conversions themselves are one instruction where the float is
# in range (_rt.f2i), and libm's rounding only beyond it, out of line: on x86-64 before SSE4.1
# trunc(), floor(), ceil() and nearbyint() are calls, which LLVM would otherwise make ahead of
# the test that almost always avoids them.


def pys_fdiv(a: float, b: float) -> float:
    if b == 0.0:
        raise ZeroDivisionError("float division by zero")
    return _rt.fdiv(a, b)


def pys_f2i(d: float) -> int:
    if d != d:
        raise ValueError("cannot convert float NaN to integer")
    if abs(d) == math.inf:
        raise OverflowError("cannot convert float infinity to integer")
    if not (d >= -9223372036854775808.0 and d < 9223372036854775808.0):
        raise OverflowError("float too large for a 64-bit int")
    return _rt.f2i(d)


@_rt.cold
def cmp_if_whole(i: int, d: float) -> int:
    # pys_cmp_if past 2**53: the whole parts first, then what d has beyond its own
    if d != d:
        return 2
    if d >= 9223372036854775808.0:
        return -1
    if d < -9223372036854775808.0:
        return 1
    t = _rt.ftrunc(d)
    j = _rt.f2i(t)
    if i != j:
        return -1 if i < j else 1
    return -1 if d > t else 1 if d < t else 0


def pys_cmp_if(i: int, d: float) -> int:
    # the exact order of an int and a float: -1, 0, 1, or 2 if unordered. An int of at most 2**53
    # in magnitude converts exactly, so comparing floats decides (with a NaN, none holds)
    if _rt.ule(_rt.wrap_add(i, 9007199254740992), 18014398509481984):
        x = float(i)
        return -1 if d > x else 1 if d < x else 0 if d == x else 2
    return cmp_if_whole(i, d)


@_rt.cold
def round_far(d: float) -> int:
    return pys_f2i(_rt.frint(d))


def pys_round(d: float) -> int:
    # round(d): half to even. Below 2**52 in magnitude, adding and then subtracting 2**52 with
    # d's sign rounds d to a whole float in the default rounding mode, exactly; from there d is whole
    if abs(d) < 4503599627370496.0:
        big = _rt.copysign(4503599627370496.0, d)
        r = d + big
        return _rt.f2i(r - big)
    return round_far(d)


@_rt.cold
def floor_far(d: float) -> int:
    return pys_f2i(_rt.ffloor(d))


@_rt.cold
def ceil_far(d: float) -> int:
    return pys_f2i(_rt.fceil(d))


@_rt.cold
def trunc_far(d: float) -> int:
    return pys_f2i(_rt.ftrunc(d))


@_rt.unchecked
def pys_floor(d: float) -> int:
    # math.floor(d): where the conversion is defined it truncates toward 0, and a negative d
    # below its truncation is one less (a NaN fails both tests)
    if d >= -9223372036854775808.0 and d < 9223372036854775808.0:
        t = _rt.f2i(d)
        return t - (1 if d < float(t) else 0)
    return floor_far(d)


@_rt.unchecked
def pys_ceil(d: float) -> int:
    # math.ceil(d): as pys_floor, one more above the truncation
    if d >= -9223372036854775808.0 and d < 9223372036854775808.0:
        t = _rt.f2i(d)
        return t + (1 if d > float(t) else 0)
    return ceil_far(d)


def pys_m_trunc(x: float) -> int:
    # math.trunc(x): the conversion truncates wherever it is defined
    if x >= -9223372036854775808.0 and x < 9223372036854775808.0:
        return _rt.f2i(x)
    return trunc_far(x)


def pys_m_isfinite(x: float) -> int:
    return 1 if abs(x) < math.inf else 0


def pys_m_isinf(x: float) -> int:
    return 1 if abs(x) == math.inf else 0


def pys_m_isnan(x: float) -> int:
    return 1 if x != x else 0


def pys_m_copysign(x: float, y: float) -> float:
    return _rt.copysign(x, y)


# ---------- strs: concatenation and repetition (runtime.c's Str) ----------
# A str is its header (length, cached dict hash, cached code-point count + 1 or 0) and its
# bytes with a NUL after them. A new one comes from pys_rt_raw, the collector's allocation that
# zeroes nothing: every byte of it is written here.


def pys_rt_raw(n: int) -> _rt.Ptr: ...


@_rt.unchecked
def str_bytes(s: str) -> _rt.Ptr:
    return _rt.offset(s, _rt.sizeof("Str"))


@_rt.unchecked
def text_cat_count(chars1: int, n: int, b: str) -> int:
    # the cached count of a str of n bytes and count chars1, followed by b, or 0 (unset). Cached
    # counts add, Unicode's too, as in the common ASCII append; but a leading continuation byte
    # can complete an invalid raw sequence at the seam
    if n == 0:
        return _rt.get(b, "Str.chars1") if len(b) != 0 else 1
    if len(b) == 0:
        return chars1
    if chars1 != 0 and _rt.get(b, "Str.chars1") != 0 and _rt.byte_at(str_bytes(b), 0) & 192 != 128:
        return chars1 + _rt.get(b, "Str.chars1") - 1
    return 0


@_rt.unchecked
def pys_str_add(a: str, b: str) -> str:
    s = pys_rt_raw(_rt.sizeof("Str") + len(a) + len(b) + 1)
    _rt.set(s, "Str.len", len(a) + len(b))
    _rt.set(s, "Str.dict_hash", 0)
    _rt.set(s, "Str.chars1", text_cat_count(_rt.get(a, "Str.chars1"), len(a), b))
    d = str_bytes(_rt.as_str(s))
    _rt.cpy(d, str_bytes(a), len(a))
    _rt.cpy(_rt.offset(d, len(a)), str_bytes(b), len(b))
    _rt.put_byte(d, len(a) + len(b), 0)
    return _rt.as_str(s)


def pys_bytes_add(a: str, b: str) -> str:
    return pys_str_add(a, b)


@_rt.unchecked
def cat_put(w: _rt.Ptr, s: str) -> _rt.Ptr:
    # s's bytes at w, and the address after them
    _rt.cpy(w, str_bytes(s), len(s))
    return _rt.offset(w, len(s))


@_rt.unchecked
def pys_str_cat(n: int, a: str, b: str, c: str, d: str, e: str, f: str, g: str, h: str) -> str:
    # the first n of its eight strs, joined: one allocation for an f-string's or a chained +'s parts
    total = 0
    chars1 = 1
    if n > 0:
        chars1 = text_cat_count(chars1, total, a)
        total += len(a)
    if n > 1:
        chars1 = text_cat_count(chars1, total, b)
        total += len(b)
    if n > 2:
        chars1 = text_cat_count(chars1, total, c)
        total += len(c)
    if n > 3:
        chars1 = text_cat_count(chars1, total, d)
        total += len(d)
    if n > 4:
        chars1 = text_cat_count(chars1, total, e)
        total += len(e)
    if n > 5:
        chars1 = text_cat_count(chars1, total, f)
        total += len(f)
    if n > 6:
        chars1 = text_cat_count(chars1, total, g)
        total += len(g)
    if n > 7:
        chars1 = text_cat_count(chars1, total, h)
        total += len(h)
    s = pys_rt_raw(_rt.sizeof("Str") + total + 1)
    _rt.set(s, "Str.len", total)
    _rt.set(s, "Str.dict_hash", 0)
    _rt.set(s, "Str.chars1", chars1)
    w = str_bytes(_rt.as_str(s))
    if n > 0:
        w = cat_put(w, a)
    if n > 1:
        w = cat_put(w, b)
    if n > 2:
        w = cat_put(w, c)
    if n > 3:
        w = cat_put(w, d)
    if n > 4:
        w = cat_put(w, e)
    if n > 5:
        w = cat_put(w, f)
    if n > 6:
        w = cat_put(w, g)
    if n > 7:
        w = cat_put(w, h)
    _rt.put_byte(w, 0, 0)
    return _rt.as_str(s)


@_rt.unchecked
def pys_str_mul(a: str, n: int) -> str:
    # a * n, as CPython's _PyBytes_Repeat: one byte is a fill, else the copied prefix doubles,
    # log2(n) copies rather than n
    if n < 0 or len(a) == 0:
        n = 0
    if n != 0 and len(a) > _rt.sdiv(9223372036854775807, n):
        raise OverflowError("repeated string is too long")
    if len(a) * n > 9223372036854775743:
        raise MemoryError
    m = len(a) * n
    k = len(a)
    s = pys_rt_raw(_rt.sizeof("Str") + m + 1)
    _rt.set(s, "Str.len", m)
    _rt.set(s, "Str.dict_hash", 0)
    d = str_bytes(_rt.as_str(s))
    _rt.put_byte(d, m, 0)
    chars1 = 0
    if n == 0:
        chars1 = 1
    elif _rt.get(a, "Str.chars1") != 0 and (n == 1 or _rt.byte_at(str_bytes(a), 0) & 192 != 128):
        chars1 = (_rt.get(a, "Str.chars1") - 1) * n + 1
    _rt.set(s, "Str.chars1", chars1)
    if k == 1:
        _rt.fill(d, _rt.byte_at(str_bytes(a), 0), m)
    elif m != 0:
        _rt.cpy(d, str_bytes(a), k)
        while k < m:
            c = k if k < m - k else m - k
            _rt.cpy(_rt.offset(d, k), d, c)
            k += c
    return _rt.as_str(s)


def pys_bytes_mul(a: str, n: int) -> str:
    return pys_str_mul(a, n)
