"""Pystachy runtime, the part written in the subset itself.

`pystachy rt runtime.py` compiles it like a program, but each `pys_*` function is defined under
its C name with runtime.c's types (bools cross as int), and the driver links it to runtime.c's
bitcode into the cached runtime (build/runtime.bc and runtime.o). runtime.c keeps a prototype of
each function moved here. Programs call these functions exactly as they call runtime.c's, so
their IR does not change.

The rules for this file: functions, imports and docstrings only (nothing runs module code); no
classes; no bools in a pys_* signature; and a function may not use the operation it implements
(math.gcd() inside pys_m_gcd would call itself). CPython can run it too, where its strs hold
bytes (as pystachy.py reads source files, as Latin-1).
"""
import math


# ---------- the math module's integer functions ----------
# The subset's arithmetic is checked, so an int result that does not fit in 64 bits raises
# CPython's OverflowError where runtime.c had to test for it, but there are no unsigned or
# 128-bit ints: these work on negated magnitudes (-2**63 has no positive counterpart) and
# reduce by a gcd before multiplying.


def pys_m_gcd(a: int, b: int) -> int:
    # Euclid on -|a| and -|b|: a floor remainder of two non-positive ints is non-positive
    x = a if a <= 0 else -a
    y = b if b <= 0 else -b
    while y != 0:
        t = x % y
        x = y
        y = t
    return -x  # gcd(-2**63, 0) = 2**63 does not fit: OverflowError


def pys_m_lcm(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    r = a // pys_m_gcd(a, b) * b
    return -r if r < 0 else r


def pys_m_isqrt(n: int) -> int:
    if n < 0:
        raise ValueError("isqrt() argument must be nonnegative")
    r = int(math.sqrt(float(n)))
    while r > 0 and r > n // r:
        r -= 1
    while r + 1 <= n // (r + 1):
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
    # r = C(n - k + i, i) after step i, which never exceeds the result: i divides r * (n - k + i),
    # so with g = gcd(r, i), i // g divides n - k + i and no step overflows unless the result does
    r = 1
    for i in range(1, k + 1):
        g = pys_m_gcd(r, i)
        r = r // g * ((n - k + i) // (i // g))
    return r


def pys_m_perm(n: int, k: int) -> int:
    nonneg(n, k)
    if k > n:
        return 0
    r = 1
    for i in range(k):
        r *= n - i
    return r
