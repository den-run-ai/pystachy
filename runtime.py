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

import _rt


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
    # r = C(n - k + i, i) after step i, which never exceeds the result. i divides r * m, so where
    # that product overflows, i // g divides m for g = gcd(r, i), and no step overflows unless the
    # result does
    r = 1
    for i in range(1, k + 1):
        m = n - k + i
        if _rt.mul_ovf(r, m):
            g = pys_m_gcd(r, i)
            r = r // g * (m // (i // g))
        else:
            r = r * m // i
    return r


def pys_m_perm(n: int, k: int) -> int:
    nonneg(n, k)
    if k > n:
        return 0
    r = 1
    for i in range(k):
        r *= n - i
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
    # whether n occurs in h at i, which leaves room for it: byte by byte while it is short, else memcmp
    m = len(n)
    if m > 8:
        return _rt.same(h, i, n, 0, m)
    for j in range(m):
        if _rt.byte(h, i + j) != _rt.byte(n, j):
            return False
    return True


def search(h: str, n: str, st: int, en: int) -> int:
    # the first i from st on where n occurs in h[:en], or -1: the next occurrence of n's first
    # byte, looked for inline over 16 bytes (dense matches) and then with memchr (sparse ones)
    m = len(n)
    if m == 0:
        return st if st <= en else -1
    first = _rt.byte(n, 0)
    last = en - m  # the last place n can start
    i = st
    while i <= last:
        stop = i + 16 if i + 16 <= last else last + 1
        while i < stop and _rt.byte(h, i) != first:
            i += 1
        if i == stop:
            if i > last:
                return -1
            i = _rt.find_byte(h, first, i, last + 1)
            if i < 0:
                return -1
        if match(h, i, n):
            return i
        i += 1
    return -1


def rsearch(h: str, n: str, st: int, en: int) -> int:
    # the last such i, or -1
    i = en - len(n)
    while i >= st:
        if match(h, i, n):
            return i
        i -= 1
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
    if en - st < len(n):
        return 0
    if len(n) == 0:
        return en - st + 1
    c = 0
    i = search(h, n, st, en)
    while i >= 0:
        c += 1
        i = search(h, n, i + len(n), en) if en - i - len(n) >= len(n) else -1
    return c


def pys_str_contains(h: str, n: str) -> int:
    return 1 if len(n) <= len(h) and search(h, n, 0, len(h)) >= 0 else 0


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
    n = len(s)
    if len(a) == 0:
        # b before each byte and at the end
        r = _rt.str_new(n + (n + 1) * len(b))
        at = 0
        for i in range(n):
            _rt.copy(r, at, b, 0, len(b))
            _rt.str_put(r, at + len(b), _rt.byte(s, i))
            at += len(b) + 1
        _rt.copy(r, at, b, 0, len(b))
        return _rt.str_done(r)
    k = 0
    j = search(s, a, 0, n) if len(a) <= n else -1
    while j >= 0:
        k += 1
        j = search(s, a, j + len(a), n) if n - j - len(a) >= len(a) else -1
    r = _rt.str_new(n + k * (len(b) - len(a)))
    i = 0
    at = 0
    j = search(s, a, 0, n) if k > 0 else -1
    while j >= 0:
        _rt.copy(r, at, s, i, j - i)
        _rt.copy(r, at + j - i, b, 0, len(b))
        at += j - i + len(b)
        i = j + len(a)
        j = search(s, a, i, n) if n - i >= len(a) else -1
    _rt.copy(r, at, s, i, n - i)
    return _rt.str_done(r)


def ws(c: int) -> bool:
    return c == 32 or (c >= 9 and c <= 13) or (c >= 28 and c <= 31)


def stripped(c: int, cs: str) -> bool:
    # whether strip() removes byte c: one of cs, or whitespace if cs was omitted (null)
    if _rt.null(cs):
        return ws(c)
    for i in range(len(cs)):
        if _rt.byte(cs, i) == c:
            return True
    return False


def strip(s: str, cs: str, m: int) -> str:
    # m: 1 left, 2 right, 3 both
    i = 0
    j = len(s)
    if m & 1:
        while i < j and stripped(_rt.byte(s, i), cs):
            i += 1
    if m & 2:
        while j > i and stripped(_rt.byte(s, j - 1), cs):
            j -= 1
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


def every(s: str, k: int) -> int:
    # all bytes are: 0 digits, 1 letters, 2 either, 3 whitespace; and there is one
    if len(s) == 0:
        return 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        d = digit(c)
        a = lowc(c | 32)
        if not (d if k == 0 else a if k == 1 else d or a if k == 2 else ws(c)):
            return 0
    return 1


def cased(s: str, up: bool) -> int:
    # isupper / islower
    seen = 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if lowc(c):
            if up:
                return 0
            seen = 1
        if upc(c):
            if not up:
                return 0
            seen = 1
    return seen


def pys_str_isdigit(s: str) -> int:
    return every(s, 0)


def pys_str_isalpha(s: str) -> int:
    return every(s, 1)


def pys_str_isalnum(s: str) -> int:
    return every(s, 2)


def pys_str_isspace(s: str) -> int:
    return every(s, 3)


def pys_str_isupper(s: str) -> int:
    return cased(s, True)


def pys_str_islower(s: str) -> int:
    return cased(s, False)


def pys_str_isdecimal(s: str) -> int:
    return every(s, 0)


def pys_str_isnumeric(s: str) -> int:
    return every(s, 0)


def pys_str_isascii(s: str) -> int:
    for i in range(len(s)):
        if _rt.byte(s, i) > 127:
            return 0
    return 1


def mapcase(s: str, how: int) -> str:
    # 0 lower, 1 upper, 2 swap: ASCII letters only (one loop per case, which LLVM vectorizes)
    n = len(s)
    r = _rt.str_new(n)
    if how == 0:
        for i in range(n):
            c = _rt.byte(s, i)
            _rt.str_put(r, i, c | 32 if upc(c) else c)
    elif how == 1:
        for i in range(n):
            c = _rt.byte(s, i)
            _rt.str_put(r, i, c & 223 if lowc(c) else c)
    else:
        for i in range(n):
            c = _rt.byte(s, i)
            _rt.str_put(r, i, c ^ 32 if lowc(c) or upc(c) else c)
    return _rt.str_done(r)


def pys_str_upper(s: str) -> str:
    return mapcase(s, 1)


def pys_str_lower(s: str) -> str:
    return mapcase(s, 0)


def pys_str_casefold(s: str) -> str:
    return mapcase(s, 0)


def pys_str_swapcase(s: str) -> str:
    return mapcase(s, 2)


def pys_str_capitalize(s: str) -> str:
    r = _rt.str_new(len(s))
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (i == 0 and lowc(c)) or (i > 0 and upc(c)):
            c ^= 32
        _rt.str_put(r, i, c)
    return _rt.str_done(r)


def pys_str_title(s: str) -> str:
    # a letter after a letter is lowered, any other raised
    r = _rt.str_new(len(s))
    prev = False
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if (prev and upc(c)) or (not prev and lowc(c)):
            _rt.str_put(r, i, c ^ 32)
        else:
            _rt.str_put(r, i, c)
        prev = lowc(c) or upc(c)
    return _rt.str_done(r)


def pys_str_istitle(s: str) -> int:
    # CPython's istitle, over ASCII letters
    prev = False
    seen = 0
    for i in range(len(s)):
        c = _rt.byte(s, i)
        if upc(c):
            if prev:
                return 0
            prev = True
            seen = 1
        elif lowc(c):
            if not prev:
                return 0
            prev = True
            seen = 1
        else:
            prev = False
    return seen


def ulen(s: str) -> int:
    # the length in characters: the bytes that do not continue a UTF-8 sequence
    k = 0
    for i in range(len(s)):
        if _rt.byte(s, i) & 192 != 128:
            k += 1
    return k


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
    if gap > (9223372036854775807 - len(s)) // len(f):
        raise MemoryError
    r = _rt.str_new(len(s) + gap * len(f))
    at = 0
    for i in range(gap):
        if i == left:
            _rt.copy(r, at, s, 0, len(s))
            at += len(s)
        _rt.copy(r, at, f, 0, len(f))
        at += len(f)
    if left == gap:
        _rt.copy(r, at, s, 0, len(s))
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
    for i in range(z):
        _rt.str_put(r, i, 48)
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
    # two passes: the length, then the bytes
    r = _rt.str_new(0)
    for k in range(2):
        col = 0
        at = 0
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
                elif c & 192 != 128:
                    col += 1
        if k == 0:
            r = _rt.str_new(at)
    return _rt.str_done(r)


def pys_str_join(sep: str, l: list[str]) -> str:
    n = 0
    for i in range(len(l)):
        n += len(l[i]) + (len(sep) if i > 0 else 0)
    r = _rt.str_new(n)
    at = 0
    for i in range(len(l)):
        if i > 0:
            _rt.copy(r, at, sep, 0, len(sep))
            at += len(sep)
        x = l[i]
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
            while i < n and ws(_rt.byte(s, i)):
                i += 1
            if i >= n:
                return out
            if left == 0:
                out.append(s[i:])  # the rest, as it is
                return out
            left -= 1
            j = i
            while j < n and not ws(_rt.byte(s, j)):
                j += 1
            out.append(s[i:j])
            i = j
    if len(sep) == 0:
        raise ValueError("empty separator")
    while left != 0:
        j = search(s, sep, i, n) if n - i >= len(sep) else -1
        if j < 0:
            break
        left -= 1
        out.append(s[i:j])
        i = j + len(sep)
    out.append(s[i:])
    return out


def pys_str_rsplit(s: str, sep: str, maxsplit: int) -> list[str]:
    # split from the right; the parts stay in order
    out: list[str] = []
    j = len(s)
    left = maxsplit if maxsplit >= 0 else 9223372036854775807
    if _rt.null(sep):
        while True:
            while j > 0 and ws(_rt.byte(s, j - 1)):
                j -= 1
            if j <= 0:
                break
            if left == 0:
                out.append(s[:j])
                break
            left -= 1
            i = j
            while i > 0 and not ws(_rt.byte(s, i - 1)):
                i -= 1
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


# ---------- dict hashing ----------
# The dicts themselves stay in runtime.c (their tables are raw int32 and uint64 arrays), which
# calls these on every lookup; LLVM inlines them there, since the two are one module once
# linked. The arithmetic wraps, as C's unsigned arithmetic does, and the shifts are logical.


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


# ---------- formatting: f"{x:spec}" ----------
# CPython's format-spec mini-language for int (and bool), float and str:
# [[fill]align][sign][z][#][0][width][grouping][.precision][type]. Widths count code points.
# runtime.c's pys_format calls these by the value's type (other types accept only an empty spec),
# and the digits of a float come from runtime.c's pys_fmt_float, which uses snprintf.


def pys_fmt_float(m: float, ty: int, prec: int, alt: int) -> str: ...


def uoff(s: str, k: int) -> int:
    # the byte offset of code point k
    i = 0
    while i < len(s) and k > 0:
        i += 1
        while i < len(s) and _rt.byte(s, i) & 192 == 128:
            i += 1
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


def tyname(kind: int) -> str:
    return "int" if kind == 0 else "bool" if kind == 1 else "float" if kind == 2 else "str"


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
    # kind: 0 int, 1 bool, 2 float, 3 str (iv, fv or sv is the value)
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
    if n - p > 1:
        raise ValueError(f"Invalid format specifier '{spec}' for object of type '{tyname(kind)}'")
    ty = _rt.byte(spec, p) if p < n else 0
    if ty == 0 and kind == 3:
        ty = 115
    if ty == 0 and kind != 2:
        ty = 100
    if sep != 0 and not among(ty, "defgEFG%") and not (sep == 95 and ty != 0 and among(ty, "boxX")):
        raise ValueError(f"Cannot specify '{chr(sep)}' with '{chr(ty)}'.")
    body = ""
    pre = 0  # bytes of sign and prefix, before '=' padding
    if kind == 3:
        if ty != 115:
            raise ValueError(f"Unknown format code '{chr(ty)}' for object of type 'str'")
        if sign != 0:
            raise ValueError("Space not allowed in string format specifier" if sign == 32 else "Sign not allowed in string format specifier")
        if zneg:
            raise ValueError("Negative zero coercion (z) not allowed in string format specifier")
        if alt:
            raise ValueError("Alternate form (#) not allowed in string format specifier")
        if align == 61:
            raise ValueError("'=' alignment not allowed in string format specifier")
        body = sv[: uoff(sv, prec)] if prec >= 0 else sv
    elif kind <= 1 and ty != 0 and among(ty, "bcdoxXn"):
        if prec >= 0:
            raise ValueError("Precision not allowed in integer format specifier")
        if zneg:
            raise ValueError("Negative zero coercion (z) not allowed in integer format specifier")
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
            head = "-" if iv < 0 else chr(sign) if sign == 43 or sign == 32 else ""
            if alt and base != 10:
                head = head + "0" + ("X" if ty == 88 else "x" if ty == 120 else chr(ty))
            pre = len(head)
            minw = width - pre if fill == "0" and align == 61 else 0
            body = head + group(_rt.str_done(dg), sep, 3 if base == 10 else 4, minw)
    else:
        # a float, or an int with a float type
        x = fv if kind == 2 else float(iv)
        if ty != 0 and not among(ty, "eEfFgGn%"):
            raise ValueError(f"Unknown format code '{chr(ty)}' for object of type '{tyname(kind)}'")
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
    if align == 61:
        return body[:pre] + fill * gap + body[pre:]
    left = 0 if align == 60 else gap // 2 if align == 94 else gap
    return fill * left + body + fill * (gap - left)


def pys_format_str(s: str, spec: str) -> str:
    return fmt(3, 0, 0.0, s, spec)


def pys_format_int(v: int, isbool: int, spec: str) -> str:
    return fmt(1 if isbool != 0 else 0, v, 0.0, "", spec)


def pys_format_float(x: float, spec: str) -> str:
    return fmt(2, 0, x, "", spec)
