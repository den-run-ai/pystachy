"""Functions to convert between Python values and C structs.
Python bytes objects are used to hold the data representing the C struct.
The format string (explained below) describes the layout of data
in the C struct.

The optional first format char indicates byte order, size and alignment:
  @: native order, size & alignment (default)
  =: native order, std. size & alignment
  <: little-endian, std. size & alignment
  >: big-endian, std. size & alignment
  !: same as >

The remaining characters indicate types of args and must match exactly;
these can be preceded by a decimal repeat count:
  x: pad byte (no data); c: char; b: signed byte; B: unsigned byte;
  ?: _Bool; h: short; H: unsigned short; i: int; I: unsigned int;
  l: long; L: unsigned long; q: long long; Q: unsigned long long;
  f: float; d: double; e: half-float;
Special cases (preceding decimal count indicates length):
  s: byte string (array of char); p: Pascal string (with count byte).
Special cases (only available in native format):
  n: ssize_t; N: size_t;
  P: an integer type that is wide enough to hold a pointer.
Whitespace between formats is ignored.

The variable struct.error is an exception raised on errors.
"""
# _struct for Pystachy: CPython builds _struct into its interpreter (Modules/_struct.c), so
# Pystachy loads this port of it for import _struct (specs.STANDINS), which Lib/struct.py imports.
# What unpack() gives depends on its format, so the compiler parses a format it knows as the
# program compiles (a literal, a module's constant, a Struct's format) and makes each call of
# pack(), unpack(), unpack_from(), iter_unpack() and calcsize() one of the functions below for
# each item, of its type (Gen.struct_call); a format the program makes as it runs is a
# compile-time error there, but calcsize() takes one. The values and errors are those of the C
# module on x86-64 Linux: native sizes and alignment are LP64's, the native order little-endian.
# Floats are packed and unpacked through math.frexp() and ldexp(), exactly but for the payload
# of a NaN, which is the quiet one, as float('nan') has. The docstrings are CPython 3.13.16's.
import math

__all__ = ["calcsize", "pack", "pack_into", "unpack", "unpack_from", "iter_unpack", "Struct", "error"]


class error(Exception):
    pass


def _clearcache() -> None:
    """Clear the internal cache."""
    # (Pystachy keeps no cache of formats: the compiler parses them)


# the size of each format character in the native table (x86-64 Linux, LP64), which is its
# alignment too, and in the standard one, which aligns nothing and has no n, N and P
_NATIVE: dict[str, int] = {"x": 1, "c": 1, "b": 1, "B": 1, "?": 1, "h": 2, "H": 2, "i": 4, "I": 4, "l": 8, "L": 8,
                           "q": 8, "Q": 8, "n": 8, "N": 8, "e": 2, "f": 4, "d": 8, "s": 1, "p": 1, "P": 8}
_STANDARD: dict[str, int] = {"x": 1, "c": 1, "b": 1, "B": 1, "?": 1, "h": 2, "H": 2, "i": 4, "I": 4, "l": 4, "L": 4,
                             "q": 8, "Q": 8, "e": 2, "f": 4, "d": 8, "s": 1, "p": 1}
_MAX = 9223372036854775807  # (PY_SSIZE_T_MAX)


def calcsize(format: str, /) -> int:
    """Return size in bytes of the struct described by the format string."""
    # (CPython's prepare_s: the byte order only as the first character, whitespace between
    # items, a decimal count before a code, native alignment before an item)
    if "\x00" in format:
        raise error("embedded null character")
    i = 0
    n = len(format)
    native = True
    if n > 0 and format[0] in "@=<>!":
        native = format[0] == "@"
        i = 1
    size = 0
    while i < n:
        c = format[i]
        i += 1
        if c in " \t\n\r\x0b\x0c":
            continue
        num = 1
        if "0" <= c <= "9":
            num = ord(c) - 48
            while i < n and "0" <= format[i] <= "9":
                d = ord(format[i]) - 48
                if num > (_MAX - d) // 10:
                    raise error("total struct size too long")
                num = num * 10 + d
                i += 1
            if i >= n:
                raise error("repeat count given without format specifier")
            c = format[i]
            i += 1
        table = _NATIVE if native else _STANDARD
        if c not in table:
            raise error("bad char in struct format")
        itemsize = table[c]
        if native and size > 0 and itemsize > 1:
            size += (itemsize - 1) - (size - 1) % itemsize
        if num > (_MAX - size) // itemsize:
            raise error("total struct size too long")
        size += num * itemsize
    return size


def _range(code: str, size: int, signed: bool) -> str:
    # CPython's struct.error for a value out of the range of code's size bytes (_range_error)
    if size == 8:
        return f"'{code}' format requires -9223372036854775808 <= number <= 9223372036854775807" if signed else f"'{code}' format requires 0 <= number <= 18446744073709551615"
    top = 1 << (8 * size)
    return f"'{code}' format requires {-(top // 2)} <= number <= {top // 2 - 1}" if signed else f"'{code}' format requires 0 <= number <= {top - 1}"


def _check_int(code: str, v: int, size: int, signed: bool) -> int:
    # v, which code's size bytes hold; CPython's struct.error for another
    if signed:
        if size < 8 and (v < -(1 << (8 * size - 1)) or v >= 1 << (8 * size - 1)):
            raise error(_range(code, size, True))
    elif v < 0 or (size < 8 and v >= 1 << (8 * size)):
        raise error(_range(code, size, False))
    return v


def _pack_int(code: str, v: int, size: int, signed: bool, little: bool) -> bytes:
    # an integer of code's size bytes, in two's complement where it is signed
    _check_int(code, v, size, signed)
    out = [0] * size
    for i in range(size):
        out[i if little else size - 1 - i] = v & 255
        v >>= 8
    return bytes(out)


def _unpack_int(b: bytes, at: int, size: int, signed: bool, little: bool) -> int:
    # the integer of size bytes at b[at]: an unsigned 8-byte one from 2**63 on is no Pystachy int
    first = b[at + size - 1] if little else b[at]
    if not signed and size == 8 and first >= 128:
        raise OverflowError("integer result does not fit in 64 bits")
    v = first - 256 if signed and first >= 128 else first
    for i in range(1, size):
        v = v * 256 + (b[at + size - 1 - i] if little else b[at + i])
    return v


def _bytes(hi: int, lo: int, size: int, little: bool) -> bytes:
    # size bytes of the bits hi (the high 32 bits) and lo (the low 32): the low byte first where
    # little, else the high one
    out = [0] * size
    for k in range(size):
        x = (lo >> (8 * k)) & 255 if k < 4 else (hi >> (8 * (k - 4))) & 255
        out[k if little else size - 1 - k] = x
    return bytes(out)


def _pack_float(code: str, v: float, little: bool) -> bytes:
    # an IEEE 754 binary16 (e), binary32 (f) or binary64 (d), as CPython's PyFloat_Pack2, 4 and 8
    # (Objects/floatobject.c) make them on x86-64: e rounds as PyFloat_Pack2 does, f as a C cast
    # to float (to nearest, ties to even), d is the double's bits
    sign = 1 if math.copysign(1.0, v) < 0 else 0
    if code == "e":
        return _bytes(0, _half(v, sign), 2, little)
    if code == "f":
        return _bytes(0, _single(v, sign), 4, little)
    hi = sign << 31
    lo = 0
    if math.isnan(v):
        hi |= 0x7FF80000
    elif math.isinf(v):
        hi |= 0x7FF00000
    elif v != 0.0:
        m, e = math.frexp(abs(v))
        if e - 1 >= -1022:
            frac = int((m * 2.0 - 1.0) * 4503599627370496.0)  # (52 bits, exactly)
            hi |= (e - 1 + 1023) << 20 | frac >> 32
            lo = frac & 0xFFFFFFFF
        else:
            frac = int(math.ldexp(abs(v), 1074))  # (a subnormal's)
            hi |= frac >> 32
            lo = frac & 0xFFFFFFFF
    return _bytes(hi, lo, 8, little)


def _round_even(q: float) -> int:
    # q, at least 0, to the nearest integer, ties to even
    n = int(q)
    r = q - n
    if r > 0.5 or (r == 0.5 and n % 2 == 1):
        n += 1
    return n


def _single(v: float, sign: int) -> int:
    # the binary32 bits of v (with sign), or OverflowError where v is finite but rounds to infinity
    if math.isnan(v):
        return sign << 31 | 0x7FC00000
    if math.isinf(v):
        return sign << 31 | 0x7F800000
    if v == 0.0:
        return sign << 31
    m, e = math.frexp(abs(v))
    if e - 1 < -126:
        k = _round_even(math.ldexp(abs(v), 149))  # (a subnormal: 2**23 is the least normal's bits)
        return sign << 31 | k
    n = _round_even(m * 16777216.0)  # (24 bits, from 2**23)
    if n == 16777216:
        n = 8388608
        e += 1
    if e - 1 > 127:
        raise OverflowError("float too large to pack with f format")
    return sign << 31 | (e - 1 + 127) << 23 | (n - 8388608)


def _half(v: float, sign: int) -> int:
    # the binary16 bits of v (with sign), as PyFloat_Pack2 rounds them
    if v == 0.0:
        return sign << 15
    if math.isinf(v):
        return sign << 15 | 0x1F << 10
    if math.isnan(v):
        return sign << 15 | 0x1F << 10 | 512
    f, e = math.frexp(abs(v))
    f *= 2.0
    e -= 1
    if e >= 16:
        raise OverflowError("float too large to pack with e format")
    if e < -25:
        f = 0.0
        e = 0
    elif e < -14:
        f = math.ldexp(f, 14 + e)
        e = 0
    else:
        e += 15
        f -= 1.0
    f *= 1024.0
    bits = int(f)
    if f - bits > 0.5 or (f - bits == 0.5 and bits % 2 == 1):
        bits += 1
        if bits == 1024:
            bits = 0
            e += 1
            if e == 31:
                raise OverflowError("float too large to pack with e format")
    return sign << 15 | e << 10 | bits


def _unpack_float(code: str, b: bytes, at: int, little: bool) -> float:
    # the binary16, binary32 or binary64 at b[at]
    size = 2 if code == "e" else 4 if code == "f" else 8
    hi = 0
    lo = 0
    for i in range(size):
        y = b[at + size - 1 - i] if little else b[at + i]  # (the bytes from the most significant)
        k = size - 1 - i
        if k < 4:
            lo |= y << (8 * k)
        else:
            hi |= y << (8 * (k - 4))
    if code == "d":
        sign = hi >> 31
        exp = (hi >> 20) & 0x7FF
        frac = (hi & 0xFFFFF) << 32 | lo
        bias = 1075
        top = 0x7FF
        whole = 4503599627370496
    elif code == "f":
        sign = lo >> 31
        exp = (lo >> 23) & 0xFF
        frac = lo & 0x7FFFFF
        bias = 150
        top = 0xFF
        whole = 8388608
    else:
        sign = lo >> 15
        exp = (lo >> 10) & 0x1F
        frac = lo & 0x3FF
        bias = 25
        top = 0x1F
        whole = 1024
    if exp == top:
        x = math.inf if frac == 0 else math.nan
    elif exp == 0:
        x = math.ldexp(float(frac), 1 - bias)
    else:
        x = math.ldexp(float(frac + whole), exp - bias)
    return -x if sign else x


def _pack_bool(v: bool) -> bytes:
    return b"\x01" if v else b"\x00"


def _unpack_bool(b: bytes, at: int) -> bool:
    return b[at] != 0


def _unpack_bytes(b: bytes, at: int, n: int) -> bytes:
    return b[at : at + n]


def _pack_char(v: bytes) -> bytes:
    if len(v) != 1:
        raise error("char format requires a bytes object of length 1")
    return v


def _pack_bytes(v: bytes, n: int, pascal: bool) -> bytes:
    # an s (pascal: p, with its length first) of n bytes: v cut or padded with zeros
    if not pascal:
        return v[:n] + bytes(n - len(v)) if len(v) < n else v[:n]
    if n == 0:
        return b""
    k = len(v) if len(v) < n - 1 else n - 1
    return bytes([k if k < 255 else 255]) + v[:k] + bytes(n - 1 - k)


def _unpack_pascal(b: bytes, at: int, n: int) -> bytes:
    if n == 0:
        return b""
    k = b[at]
    if k >= n:
        k = n - 1
    return b[at + 1 : at + 1 + k]


def _need(b: bytes | bytearray, size: int) -> None:
    # unpack()'s buffer: exactly size bytes
    if len(b) != size:
        raise error(f"unpack requires a buffer of {size} bytes")


def _offset(b: bytes | bytearray, offset: int, size: int) -> int:
    # unpack_from()'s offset in b of size bytes, from the end of b where it is negative
    n = len(b)
    if offset < 0:
        if offset + size > 0:
            raise error(f"not enough data to unpack {size} bytes at offset {offset}")
        if offset + n < 0:
            raise error(f"offset {offset} out of range for {n}-byte buffer")
        offset += n
    if n - offset < size:
        raise error(f"unpack_from requires a buffer of at least {size + offset} bytes for unpacking {size} bytes at offset {offset} (actual buffer size is {n})")
    return offset


def _into(b: bytes | bytearray, offset: int, size: int) -> int:
    # pack_into()'s offset in b for size bytes, from the end of b where it is negative
    n = len(b)
    if offset < 0:
        if offset + size > 0:
            raise error(f"no space to pack {size} bytes at offset {offset}")
        if offset + n < 0:
            raise error(f"offset {offset} out of range for {n}-byte buffer")
        offset += n
    if n - offset < size:
        raise error(f"pack_into requires a buffer of at least {size + offset} bytes for packing {size} bytes at offset {offset} (actual buffer size is {n})")
    return offset


def _offsets(b: bytes | bytearray, size: int) -> list[int]:
    # iter_unpack()'s: where each struct of size bytes starts in b
    if size == 0:
        raise error("cannot iteratively unpack with a struct of length 0")
    if len(b) % size != 0:
        raise error(f"iterative unpacking requires a buffer of a multiple of {size} bytes")
    return [i for i in range(0, len(b), size)]


def _known(name: str) -> str:
    # (what each of the functions below says where Pystachy compiles it, not a call of it: the
    # compiler makes the call, Gen.struct_call)
    return f"_struct.{name}() is supported where its format is known as the program compiles, called by its name: the compiler makes the call"


def pack(format: str, /, *v) -> bytes:
    """pack(format, v1, v2, ...) -> bytes

Return a bytes object containing the values v1, v2, ... packed according
to the format string.  See help(struct) for more on format strings."""
    raise NotImplementedError(_known("pack"))


def unpack(format: str, buffer: bytes, /):
    """Return a tuple containing values unpacked according to the format string.

The buffer's size in bytes must be calcsize(format).

See help(struct) for more on format strings."""
    raise NotImplementedError(_known("unpack"))


def unpack_from(format: str, /, buffer: bytes, offset: int = 0):
    """Return a tuple containing values unpacked according to the format string.

The buffer's size, minus offset, must be at least calcsize(format).
A negative offset counts from the end of the buffer.

See help(struct) for more on format strings."""
    raise NotImplementedError(_known("unpack_from"))


def iter_unpack(format: str, buffer: bytes, /):
    """Return an iterator yielding tuples unpacked from the given bytes.

The bytes are unpacked according to the format string, like
a repeated invocation of unpack_from().

Requires that the bytes length be a multiple of the format struct size."""
    raise NotImplementedError(_known("iter_unpack"))


def pack_into(format: str, buffer, offset: int, /, *v) -> None:
    """pack_into(format, buffer, offset, v1, v2, ...)

Pack the values v1, v2, ... according to the format string and write
the packed bytes into the writable buffer buf starting at offset.  Note
that the offset is a required argument.  A negative offset counts from
the end of the buffer.  See help(struct) for more on format strings."""
    raise NotImplementedError(_known("pack_into"))


class Struct:
    """Struct(fmt) --> compiled struct object

"""
    # (a class that specializes on its format, a literal (Gen.literal_class), so that its
    # methods' calls of the functions above know it as the program compiles)

    def __init__(self, format):
        self.format = format
        self.size = calcsize(format)

    def pack(self, *v):
        """S.pack(v1, v2, ...) -> bytes

Return a bytes object containing values v1, v2, ... packed according
to the format string S.format.  See help(struct) for more on format
strings."""
        return pack(self.format, *v)

    def pack_into(self, buffer, offset, *v):
        """S.pack_into(buffer, offset, v1, v2, ...)

Pack the values v1, v2, ... according to the format string S.format
and write the packed bytes into the writable buffer buf starting at
offset.  Note that the offset is a required argument.  See
help(struct) for more on format strings."""
        pack_into(self.format, buffer, offset, *v)

    def unpack(self, buffer, /):
        """Return a tuple containing unpacked values.

Unpack according to the format string Struct.format. The buffer's size
in bytes must be Struct.size.

See help(struct) for more on format strings."""
        return unpack(self.format, buffer)

    def unpack_from(self, buffer, offset=0):
        """Return a tuple containing unpacked values.

Values are unpacked according to the format string Struct.format.

The buffer's size in bytes, starting at position offset, must be
at least Struct.size.  A negative offset counts from the end of the
buffer.

See help(struct) for more on format strings."""
        return unpack_from(self.format, buffer, offset)

    def iter_unpack(self, buffer, /):
        """Return an iterator yielding tuples.

Tuples are unpacked from the given bytes source, like a repeated
invocation of unpack_from().

Requires that the bytes length be a multiple of the struct size."""
        return iter_unpack(self.format, buffer)
