"""CPython's version of runtime.py's primitives (pystachy.py's RTL table), for running runtime.py
on CPython: tools/rtcheck.py tests its functions there against CPython's own builtins.

A str holds bytes in Pystachy; here it holds one character per byte (as Latin-1 decodes them),
as pystachy.py reads its sources, so len(), indexing and slicing agree. str_new gives a bytearray,
which str_put and copy change, and str_done turns into such a str.
"""
import math
import struct
from fractions import Fraction

from rt_heap import Fault, Ptr, nsw, shift  # noqa: F401  (a raw address; unchecked arithmetic, as load() rewrites it)

M64 = (1 << 64) - 1


def unchecked(f):
    # (CPython's ints do not wrap: rt_heap.load() makes a function's + - * << >> what they are compiled)
    return f


def cold(f):
    return f


MACHINE = ("nil", "ptr", "addr", "ref", "as_str", "word", "put", "byte_at", "put_byte", "i32_at", "put_i32", "at",
           "offset", "get", "set", "getp", "setp", "field", "sizeof", "move", "cpy", "fill", "cmp")


def _machine(name):
    def primitive(*args):
        raise NotImplementedError(f"_rt.{name}: runtime.py's machine memory needs a heap here (rt_heap.py, as tools/rtcheck.py gives it)")
    return primitive


for _name in MACHINE:
    globals()[_name] = _machine(_name)


def use(table):
    # machine memory from rt_heap.primitives(heap): tools/rtcheck.py runs the memory code on it
    for name in MACHINE + ("null",):
        globals()[name] = table[name]


def i64(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


def byte(s, i):
    if not 0 <= i < len(s):
        raise IndexError("string index out of range")
    return s[i] if isinstance(s, bytearray) else ord(s[i])


def str_new(n):
    if not 0 <= n <= (1 << 63) - 18:
        raise MemoryError()
    return bytearray(n)


def str_put(s, i, b):
    if not 0 <= i < len(s):
        raise IndexError("string index out of range")
    if not 0 <= b <= 255:
        raise ValueError("byte must be in range(0, 256)")
    s[i] = b


def str_done(s):
    # the builder is emptied, so a later str_put or copy into it fails here as it should
    r = bytes(s).decode("latin-1")
    s.clear()
    return r


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


def ashr(a, n):
    return i64(a) >> (n & 63)


def ctlz(a):
    return 64 - (a & M64).bit_length()


def ctpop(a):
    return (a & M64).bit_count()


def null(s):
    return s is None


def same(a, i, b, j, n):
    if n < 0 or not 0 <= i <= len(a) - n or not 0 <= j <= len(b) - n:
        raise IndexError("compare out of range")
    return a[i : i + n] == b[j : j + n]


def find_byte(s, c, st, en):
    if not 0 <= st <= en <= len(s):
        raise IndexError("search out of range")
    if not 0 <= c <= 255:
        raise ValueError("byte must be in range(0, 256)")
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


def sdiv(a, b):
    if b == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    if a == -(1 << 63) and b == -1:
        raise OverflowError("integer result does not fit in 64 bits")
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def srem(a, b):
    if b == 0:
        raise ZeroDivisionError("integer modulo by zero")
    r = abs(a) % abs(b)
    return -r if a < 0 else r


def mul_ovf(a, b):
    return not -(1 << 63) <= a * b < 1 << 63


def mul_hi(a, b):
    return i64(((a & M64) * (b & M64)) >> 64)


def udiv_wide(hi, lo, d):
    if d == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return i64((((hi & M64) << 64) | (lo & M64)) // (d & M64))


def urem_wide(hi, lo, d):
    if d == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return i64((((hi & M64) << 64) | (lo & M64)) % (d & M64))


def float_bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def bits_float(i):
    return struct.unpack("<d", struct.pack("<q", i))[0]


def fma(x, y, z):
    # x * y + z rounded once, with no errors: an inf or a nan where math.fma raises
    if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
        r = Fraction(x) * Fraction(y) + Fraction(z)
        if r == 0:
            # a zero product and a zero z add as two zeros do, by their signs; a product that z
            # cancels leaves +0.0
            if x == 0.0 or y == 0.0:
                return 0.0 * (math.copysign(1.0, x) * math.copysign(1.0, y)) + z
            return 0.0
        try:
            return float(r)
        except OverflowError:
            return math.inf if r > 0 else -math.inf
    if math.isnan(x) or math.isnan(y) or math.isnan(z):
        return math.nan
    if (math.isinf(x) and y == 0.0) or (math.isinf(y) and x == 0.0):
        return math.nan
    if math.isinf(x) or math.isinf(y):
        p = math.copysign(math.inf, math.copysign(1.0, x) * math.copysign(1.0, y))
        return math.nan if math.isinf(z) and z != p else p
    return z


def fdiv(x, y):
    # x / y as IEEE 754 divides: by a zero, an inf of the signs' product, or a nan for 0 / 0
    if y != 0.0:
        return x / y
    if x != x or x == 0.0:
        return math.nan
    return math.copysign(math.inf, x) * math.copysign(1.0, y)


def sqrt(x):
    return math.sqrt(x) if x >= 0.0 else math.nan if x == x else x


def find_sub(h, n, st, en):
    if not 0 <= st <= en <= len(h):
        raise IndexError("search out of range")
    return h.find(n, st, en)


class UnicodeDecodeError(UnicodeDecodeError):  # (CPython's, with the message runtime.py made)
    def __init__(self, msg):
        super().__init__("utf-8", b"", 0, 0, "")
        self.msg = msg

    def __str__(self):
        return self.msg


class UnicodeEncodeError(UnicodeEncodeError):
    def __init__(self, msg):
        super().__init__("utf-8", "", 0, 0, "")
        self.msg = msg

    def __str__(self):
        return self.msg


def fail(kind, msg):
    # raise builtin exception kind with message msg (a UnicodeDecodeError or UnicodeEncodeError,
    # whose constructor takes the parts of its message, is one whose str() is msg)
    if kind == "UnicodeDecodeError":
        raise UnicodeDecodeError(msg)
    if kind == "UnicodeEncodeError":
        raise UnicodeEncodeError(msg)
    import builtins
    raise getattr(builtins, kind)(msg)


def ftrunc(x):
    return float(math.trunc(x)) if math.isfinite(x) else x


def ffloor(x):
    return float(math.floor(x)) if math.isfinite(x) else x


def fceil(x):
    return float(math.ceil(x)) if math.isfinite(x) else x


def frint(x):
    # nearbyint in the default rounding mode: half to even
    return float(round(x)) if math.isfinite(x) else x


def copysign(x, y):
    return math.copysign(x, y)


def f2i(x):
    return int(x)


def ult(a, b):
    return (a & M64) < (b & M64)


def ule(a, b):
    return (a & M64) <= (b & M64)
