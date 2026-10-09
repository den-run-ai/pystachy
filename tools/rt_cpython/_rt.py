"""CPython's version of runtime.py's primitives (pystachy.py's RTL table), for running runtime.py
on CPython: tools/rtcheck.py tests its functions there against CPython's own builtins.

A str holds bytes in Pystachy; here it holds one character per byte (as Latin-1 decodes them),
as pystachy.py reads its sources, so len(), indexing and slicing agree. str_new gives a bytearray,
which str_put and copy change, and str_done turns into such a str.
"""
M64 = (1 << 64) - 1


def i64(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


def byte(s, i):
    if not 0 <= i < len(s):
        raise IndexError("string index out of range")
    return s[i] if isinstance(s, bytearray) else ord(s[i])


def str_new(n):
    if n < 0:
        raise MemoryError("negative size")
    return bytearray(n)


def str_put(s, i, b):
    if not 0 <= i < len(s):
        raise IndexError("string index out of range")
    if not 0 <= b <= 255:
        raise ValueError("byte must be in range(0, 256)")
    s[i] = b


def str_done(s):
    return bytes(s).decode("latin-1")


def copy(dst, at, src, lo, n):
    if n < 0 or not 0 <= at <= len(dst) - n or not 0 <= lo <= len(src) - n:
        raise IndexError("copy out of range")
    part = src[lo : lo + n]
    dst[at : at + n] = part if isinstance(part, (bytes, bytearray)) else part.encode("latin-1")


def wrap_add(a, b):
    return i64(a + b)


def wrap_sub(a, b):
    return i64(a - b)


def wrap_mul(a, b):
    return i64(a * b)


def shl(a, n):
    return i64(a << (n & 63))


def lshr(a, n):
    return i64((a & M64) >> (n & 63))


def null(s):
    return s is None


def same(a, i, b, j, n):
    if n < 0 or not 0 <= i <= len(a) - n or not 0 <= j <= len(b) - n:
        raise IndexError("compare out of range")
    return a[i : i + n] == b[j : j + n]


def find_byte(s, c, st, en):
    if not 0 <= st <= en <= len(s):
        raise IndexError("search out of range")
    i = s.find(c if isinstance(s, bytearray) else chr(c), st, en)
    return i


def udiv(a, b):
    if b == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return i64((a & M64) // (b & M64))


def urem(a, b):
    if b == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return i64((a & M64) % (b & M64))


def mul_ovf(a, b):
    return not -(1 << 63) <= a * b < 1 << 63
